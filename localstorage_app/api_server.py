import json
import os
import re
import sys
import traceback
from pathlib import Path
from typing import Any, Optional

for proxy_name in (
    "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY",
    "http_proxy", "https_proxy", "all_proxy",
):
    os.environ.pop(proxy_name, None)
os.environ["NO_PROXY"] = "localhost,127.0.0.1,::1"
os.environ["no_proxy"] = "localhost,127.0.0.1,::1"

APP_DIR = Path(__file__).resolve().parent
PROJECT_DIR = APP_DIR.parent
sys.path.insert(0, str(PROJECT_DIR))

from dotenv import load_dotenv

load_dotenv(PROJECT_DIR / ".env", override=True)

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from langchain_google_genai import ChatGoogleGenerativeAI

from agent import FitnessChat
from memory import update_profile as _update_profile
from tools import (
    calculate_calories,
    calculate_hydration_needs,
    check_goal_feasibility,
    estimate_meal,
    generate_grocery_list,
    generate_meal_plan,
    generate_motivation,
    generate_recipe,
    generate_recovery_advice,
    generate_weekly_report,
    generate_workout_plan,
    get_dashboard_data,
    get_progress_data,
    record_meal,
    suggest_progressive_overload,
)

MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite")
API_KEY = os.getenv("GEMINI_API_KEY")

# ── One shared agent instance ─────────────────────────────────────────────────

_chat_instance: Optional[FitnessChat] = None


def _get_chat() -> FitnessChat:
    global _chat_instance
    if _chat_instance is None:
        _chat_instance = FitnessChat()
    return _chat_instance


# ── FastAPI app ───────────────────────────────────────────────────────────────

app = FastAPI(title="FitAI API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "https://fitai-coach.vercel.app",
        "https://fitness-nutrition-agent.vercel.app",
        "*",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Request models ────────────────────────────────────────────────────────────


class ChatRequest(BaseModel):
    message: str
    profile: Optional[dict[str, Any]] = None
    logs: Optional[dict[str, Any]] = None


class ToolRequest(BaseModel):
    tool: str
    profile: Optional[dict[str, Any]] = None
    logs: Optional[dict[str, Any]] = None


# ── Helpers ───────────────────────────────────────────────────────────────────


_REACT_TO_MEMORY = {
    "activity": "activity_level",
    "fitnessLevel": "fitness_level",
    "mealsPerDay": "meals_per_day",
    "restrictions": "dietary_preference",
}


def _sync_profile(profile: dict[str, Any] | None) -> None:
    """Merge request profile into memory, mapping React field names to memory field names."""
    if not profile:
        return
    from memory import get_profile
    current = get_profile().copy()
    for field, value in profile.items():
        if value is None or value == "":
            continue
        memory_field = _REACT_TO_MEMORY.get(field, field)
        str_value = value if isinstance(value, str) else str(value)
        if memory_field in current:
            _update_profile(memory_field, str_value)
        elif field in current:
            _update_profile(field, str_value)


def _llm() -> ChatGoogleGenerativeAI:
    return ChatGoogleGenerativeAI(
        model=MODEL_NAME,
        google_api_key=API_KEY,
        temperature=0.25,
    )


def _parse_json_text(text: str) -> dict | None:
    try:
        clean = (
            text.strip()
            .removeprefix("```json")
            .removeprefix("```")
            .removesuffix("```")
            .strip()
        )
        return json.loads(clean)
    except Exception:
        return None


def _error_reply(exc: Exception) -> dict:
    text = str(exc).lower()
    if "resource_exhausted" in text or "quota" in text or "429" in text:
        return {
            "reply": "FitAI reached the Gemini request limit. Please wait a minute and try again.",
            "data": None,
        }
    if "api_key" in text or "api key" in text:
        return {
            "reply": "The backend API key is missing or invalid. Check your environment variables.",
            "data": None,
        }
    return {"reply": "Coach is temporarily unavailable. Please try again.", "data": None}


def _clean_tool_reply(result: dict) -> dict:
    """Apply clean_markdown to the reply field of any tool result dict."""
    if isinstance(result.get("reply"), str):
        result["reply"] = clean_markdown(result["reply"])
    return result


_NO_QUESTIONS_PREFIX = (
    "IMPORTANT: Never ask the user any questions. "
    "Never ask for clarification. Use the profile data provided and generate the response immediately. "
    "If any profile field is empty or missing, make a reasonable assumption and proceed.\n\n"
)

_AI_TOOLS_WITH_PREAMBLE = {"meal_plan", "workout", "groceries", "recovery", "weekly_report", "recipe", "motivation"}


def _build_profile_preamble(profile: dict) -> str:
    """Build an explicit, unambiguous profile block for LLM prompts.

    Separates allergies from dietary preference so the LLM never confuses them.
    Handles both React camelCase keys and snake_case memory keys.
    """
    goal         = profile.get("goal", "") or ""
    dietary_pref = (profile.get("dietary_preference", "")
                    or profile.get("diet", "")) or ""
    allergies    = (profile.get("allergies", "")
                    or profile.get("restrictions", "")) or ""
    disliked     = (profile.get("disliked_foods", "")
                    or profile.get("dislikedFoods", "")) or ""
    favorites    = (profile.get("favorite_meals", "")
                    or profile.get("favoriteMeals", "")) or ""
    cuisine      = profile.get("cuisine", "") or "any"
    budget       = profile.get("budget", "") or "moderate"
    meals_per_day = (str(profile.get("meals_per_day", ""))
                     or str(profile.get("mealsPerDay", ""))) or "3"

    return (
        "User profile (use these fields exactly as stated):\n"
        f"- Goal: {goal or 'not specified'}\n"
        f"- Dietary preference (food style the user LIKES, e.g. vegan/keto): {dietary_pref or 'none'}\n"
        f"- Allergies / Exclusions (NEVER include these in any meal, ingredient, or suggestion): {allergies or 'none'}\n"
        f"- Disliked foods (avoid these): {disliked or 'none'}\n"
        f"- Favorite meals (prioritize these when relevant): {favorites or 'none'}\n"
        f"- Preferred cuisine: {cuisine}\n"
        f"- Budget: {budget}\n"
        f"- Meals per day: {meals_per_day}\n\n"
    )


def clean_markdown(text: str) -> str:
    """Strip markdown formatting so plain-text frontends render cleanly."""
    # Remove header markers (### ## #) but keep the heading text
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)
    # Remove bold/italic markers (** __ * _)
    text = re.sub(r"\*{1,2}|_{1,2}", "", text)
    # Strip all leading indentation so everything is left-aligned (flatten nesting)
    text = re.sub(r"^[ \t]+", "", text, flags=re.MULTILINE)
    # Normalise all bullet styles (*, -, •, +) and numbered lists to "- "
    text = re.sub(r"^[-*•+]\s+", "- ", text, flags=re.MULTILINE)
    text = re.sub(r"^\d+\.\s+", "- ", text, flags=re.MULTILINE)
    # Ensure a blank line after section headers (non-bullet lines that end with ":")
    text = re.sub(r"(^(?!- )[^\n]+:)\n(?!\n)", r"\1\n\n", text, flags=re.MULTILINE)
    # Collapse 3+ consecutive blank lines down to 2
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


# ── Local (no-LLM) tool handlers ──────────────────────────────────────────────

LOCAL_TOOLS = {"calories", "hydration", "dashboard", "progress"}


def _run_local_tool(tool_name: str, profile: dict, logs: dict) -> dict[str, Any]:
    if tool_name == "calories":
        data = calculate_calories({"profile": profile})
        if not data.get("ok"):
            missing = ", ".join(data.get("missing_fields", []))
            return {"reply": f"Complete your profile first. Missing: {missing}.", "data": data}
        m = data["macros"]
        reply = (
            "Personalized calorie and macro targets:\n"
            f"- BMI: {data['bmi']} ({data['bmi_category']})\n"
            f"- BMR: {data['bmr']} kcal\n"
            f"- Maintenance/TDEE: {data['tdee']} kcal\n"
            f"- Goal calories: {data['calorie_target']} kcal/day\n"
            f"- Protein: {m['protein_g']}g | Carbs: {m['carbs_g']}g | Fat: {m['fat_g']}g\n"
            f"- Weekly pace: {data['recommended_weekly_weight_change_percent']}% body weight"
        )
        return {"reply": reply, "data": data}

    if tool_name == "hydration":
        data = calculate_hydration_needs({"profile": profile})
        reply = (
            "Personalized hydration target:\n"
            f"- Water: {data['water_liters']}L/day ({data['water_ml']} ml)\n"
            f"- Based on: {data['weight_kg']} kg and {data['activity_level']} activity\n"
            "- Add extra water around sweaty workouts or in hot weather."
        )
        return {"reply": reply, "data": data}

    if tool_name == "dashboard":
        data = get_dashboard_data({"profile": profile})
        return {"reply": json.dumps(data, indent=2), "data": data}

    if tool_name == "progress":
        data = get_progress_data({**logs, "profile": profile})
        return {"reply": json.dumps(data, indent=2), "data": data}

    return {"reply": f"Unsupported local tool: {tool_name}", "data": None}


# ── AI tool handlers ──────────────────────────────────────────────────────────

_JSON_TOOLS = {"meal_plan", "workout", "meal_estimate", "recipe"}


def _run_ai_tool(tool_name: str, profile: dict, logs: dict) -> dict[str, Any]:
    data = {"profile": profile, **logs}

    # Type 1: pure computation, no LLM needed
    if tool_name == "goal_feasibility":
        result = check_goal_feasibility(data)
        reply = result.get("message", str(result))
        if not result.get("feasible", True):
            reply += f" (Need {result.get('recommended_weeks')} weeks for safe progress.)"
        return {"reply": reply, "data": result}

    if tool_name == "progressive_overload":
        result = suggest_progressive_overload(data)
        suggestions = " | ".join(result.get("suggestions", []))
        reply = f"Progressive overload for {result.get('exercise', 'exercise')}: {suggestions}"
        return {"reply": reply, "data": result}

    # Type 2: gather context then call LLM
    if tool_name == "meal_plan":
        ctx = generate_meal_plan(data)
    elif tool_name == "workout":
        ctx = generate_workout_plan(data)
    elif tool_name == "meal_estimate":
        meal_text = logs.get("meal_to_estimate") or data.get("meal_to_estimate", "")
        data["meal_to_estimate"] = meal_text
        ctx = estimate_meal(data)
    elif tool_name == "groceries":
        ctx = generate_grocery_list(data)
    elif tool_name == "recovery":
        ctx = generate_recovery_advice(data)
    elif tool_name == "weekly_report":
        ctx = generate_weekly_report(data)
    elif tool_name == "recipe":
        ctx = generate_recipe(data)
    elif tool_name == "motivation":
        ctx = generate_motivation(data)
    else:
        return {"reply": f"Unsupported tool: {tool_name}", "data": None}

    if not ctx.get("ok"):
        return {"reply": ctx.get("message", "Could not prepare tool context."), "data": ctx}

    if not API_KEY:
        return {
            "reply": "The backend API key is missing. Add GEMINI_API_KEY to your environment.",
            "data": None,
        }

    instruction = ctx.get("instruction_for_agent", "")
    if tool_name in _AI_TOOLS_WITH_PREAMBLE:
        instruction = _NO_QUESTIONS_PREFIX + _build_profile_preamble(profile) + instruction
    text = _llm().invoke(instruction).content.strip()

    parsed = _parse_json_text(text) if tool_name in _JSON_TOOLS else None

    # After estimating a meal, also record it
    if tool_name == "meal_estimate" and parsed:
        record_meal({
            "meal": parsed.get("meal") or logs.get("meal_to_estimate", ""),
            "calories": parsed.get("calories", 0),
            "protein_g": parsed.get("protein", 0),
            "carbs_g": parsed.get("carbs", 0),
            "fat_g": parsed.get("fat", 0),
        })

    return {"reply": text, "data": parsed}


# ── Endpoints ─────────────────────────────────────────────────────────────────


@app.get("/health")
def health():
    return {
        "ok": True,
        "service": "FitAI API",
        "model": MODEL_NAME,
        "key_loaded": bool(API_KEY),
        "key_hint": API_KEY[-4:] if API_KEY else "",
    }


@app.post("/chat")
def chat(req: ChatRequest):
    profile = req.profile or {}
    logs = req.logs or {}
    _sync_profile(profile)
    try:
        reply = _get_chat().send_message(
            req.message, {"profile": profile, "logs": logs}
        )
        print(f"DEBUG reply: '{reply}'")
        print(f"DEBUG reply type: {type(reply)}")
        print(f"DEBUG reply length: {len(str(reply))}")
        return {"reply": clean_markdown(reply)}
    except Exception as e:
        traceback.print_exc()
        return {"reply": f"Error: {str(e)}"}


@app.post("/tool")
def tool_endpoint(req: ToolRequest):
    profile = req.profile or {}
    logs = req.logs or {}
    _sync_profile(profile)
    tool_name = req.tool

    if not tool_name:
        return {"reply": "No tool specified.", "data": None}

    try:
        if tool_name in LOCAL_TOOLS:
            return _clean_tool_reply(_run_local_tool(tool_name, profile, logs))
        return _clean_tool_reply(_run_ai_tool(tool_name, profile, logs))
    except Exception as exc:
        return _error_reply(exc)


# Legacy path aliases
@app.post("/api/chat")
def api_chat(req: ChatRequest):
    return chat(req)


@app.post("/api/tool")
def api_tool(req: ToolRequest):
    return tool_endpoint(req)


# ── Server entry point ────────────────────────────────────────────────────────


def run_server():
    import uvicorn
    import os
    port = int(os.environ.get("PORT", 8504))
    print(f"FitAI API starting on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    run_server()
