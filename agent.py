import json
import os
from typing import Any

for proxy_name in (
    "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY",
    "http_proxy", "https_proxy", "all_proxy",
):
    os.environ.pop(proxy_name, None)
os.environ["NO_PROXY"] = "localhost,127.0.0.1,::1"
os.environ["no_proxy"] = "localhost,127.0.0.1,::1"

from dotenv import load_dotenv
from langgraph.prebuilt import create_react_agent
from langchain.tools import tool
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from memory import get_profile, profile_summary, update_profile
from rag import retrieve_context
from tools import (
    calculate_calories,
    calculate_hydration_needs,
    check_goal_feasibility,
    enforce_dietary_restrictions,
    estimate_meal,
    fetch_exercises_by_muscle,
    generate_grocery_list,
    generate_meal_plan,
    generate_motivation,
    generate_recipe,
    generate_recovery_advice,
    generate_weekly_report,
    generate_workout_plan,
    get_dashboard_data,
    get_profile_data,
    get_progress_data,
    record_checkin,
    record_hydration,
    record_meal,
    record_workout,
    suggest_progressive_overload,
)

load_dotenv(dotenv_path=".env")


# ── Tool definitions ──────────────────────────────────────────────────────────

@tool
def calculate_calories_tool(profile: dict[str, Any]) -> dict[str, Any]:
    """Calculate BMI, BMR, TDEE, calorie target, and macros from a structured profile.
    ALWAYS call this when the user asks about calories, TDEE, BMI, or macros."""
    return calculate_calories({"profile": profile})


@tool
def hydration_tool(profile: dict[str, Any]) -> dict[str, Any]:
    """Calculate daily hydration target from the user profile.
    ALWAYS call this when the user asks about water intake or hydration needs."""
    return calculate_hydration_needs({"profile": profile})


@tool
def record_meal_tool(
    meal: str,
    calories: int,
    protein_g: int,
    carbs_g: int,
    fat_g: int,
    timestamp: str = "",
) -> dict[str, Any]:
    """Save a meal entry to the log. Estimate calories and macros first, then call this.
    ALWAYS call this when the user mentions eating anything."""
    return record_meal({
        "meal": meal,
        "calories": calories,
        "protein_g": protein_g,
        "carbs_g": carbs_g,
        "fat_g": fat_g,
        "timestamp": timestamp,
    })


@tool
def record_workout_tool(
    session: str,
    duration_minutes: int = 0,
    difficulty_rating: str = "",
    completed: bool = True,
    timestamp: str = "",
) -> dict[str, Any]:
    """Save a completed workout entry to the log.
    ALWAYS call this when the user mentions doing a workout or exercise session."""
    return record_workout({
        "session": session,
        "duration_minutes": duration_minutes,
        "difficulty_rating": difficulty_rating,
        "completed": completed,
        "timestamp": timestamp,
    })


@tool
def record_hydration_tool(ml: int, timestamp: str = "") -> dict[str, Any]:
    """Save water intake in millilitres.
    Call this when the user logs drinking water."""
    return record_hydration({"ml": ml, "timestamp": timestamp})


@tool
def record_checkin_tool(
    sleep_hours: float,
    mood: str,
    soreness: str,
    energy: str,
    weight: float = 0,
    timestamp: str = "",
) -> dict[str, Any]:
    """Save a daily check-in with sleep, mood, soreness, energy, and optional weight.
    Call this when the user does a daily check-in."""
    return record_checkin({
        "sleep_hours": sleep_hours,
        "mood": mood,
        "soreness": soreness,
        "energy": energy,
        "weight": weight,
        "timestamp": timestamp,
    })


@tool
def progress_tool(days: int = 7) -> dict[str, Any]:
    """Return structured meal, workout, hydration, check-in, and streak data.
    ALWAYS call this when the user asks about their progress or history."""
    return get_progress_data({"days": days})


@tool
def dashboard_tool(profile: dict[str, Any]) -> dict[str, Any]:
    """Return dashboard values: BMI, calories, protein, workouts, streak, progress.
    Call this for a full stats overview."""
    return get_dashboard_data({"profile": profile})


@tool
def profile_tool() -> dict[str, Any]:
    """Return the saved user profile as structured JSON.
    Use only when no frontend profile is available in context."""
    return get_profile_data({})


@tool
def update_profile_tool(field: str, value: str) -> dict[str, Any]:
    """Update one saved profile field (e.g. 'goal', 'weight', 'age').
    Call this when the user explicitly updates their profile."""
    before = get_profile().copy()
    update_profile(field, value)
    after = get_profile().copy()
    return {"ok": before != after, "field": field, "value": value, "profile": after}


@tool
def retrieve_knowledge_tool(query: str) -> dict[str, Any]:
    """Search the local fitness/nutrition knowledge base for relevant information.
    ALWAYS call this for broad educational questions about fitness, nutrition, or health.
    Returns {ok, found, context, message} — if found is false, answer from LLM knowledge."""
    context = retrieve_context(query)
    found = bool(context and context.strip())
    return {
        "ok": True,
        "found": found,
        "context": context,
        "message": "Knowledge found in local base." if found else "No strong match found. Use LLM knowledge.",
    }


@tool
def check_goal_feasibility_tool(
    current_weight: float,
    target_weight: float,
    timeframe_weeks: int = 12,
    goal: str = "",
) -> dict[str, Any]:
    """Check whether a weight-change goal is safe and realistic within a given timeframe.
    ALWAYS call this when the user asks if their goal is achievable or realistic."""
    return check_goal_feasibility({
        "current_weight": current_weight,
        "target_weight": target_weight,
        "timeframe_weeks": timeframe_weeks,
        "goal": goal,
    })


@tool
def suggest_progressive_overload_tool(
    exercise: str,
    reps: int = 10,
    sets: int = 3,
    weight_kg: float = 0,
    weeks_at_current: int = 1,
    fitness_level: str = "",
) -> dict[str, Any]:
    """Suggest the next progressive overload step for a specific exercise.
    ALWAYS call this when the user asks how to progress an exercise or what weight to use next."""
    return suggest_progressive_overload({
        "exercise": exercise,
        "reps": reps,
        "sets": sets,
        "weight_kg": weight_kg if weight_kg else None,
        "weeks_at_current": weeks_at_current,
        "fitness_level": fitness_level,
    })


@tool
def generate_meal_plan_tool(
    dietary_preference: str = "",
    preferred_cuisine: str = "",
    allergies: str = "",
) -> dict[str, Any]:
    """Generate a personalised daily meal plan with macros per meal.
    ALWAYS call this when the user asks for a meal plan or daily food schedule."""
    return generate_meal_plan({
        "dietary_preference": dietary_preference,
        "preferred_cuisine": preferred_cuisine,
        "allergies": allergies,
    })


@tool
def generate_workout_plan_tool(
    days_per_week: int = 3,
    equipment: str = "bodyweight only",
    training_place: str = "",
) -> dict[str, Any]:
    """Generate a personalised weekly workout plan with exercises, sets, reps, and rest.
    ALWAYS call this when the user asks for a workout plan or exercise schedule."""
    return generate_workout_plan({
        "days_per_week": days_per_week,
        "equipment": equipment,
        "training_place": training_place,
    })


@tool
def estimate_meal_tool(meal: str) -> dict[str, Any]:
    """Estimate calories and macros for a described meal.
    ALWAYS call this when the user asks to estimate or analyse a specific meal's nutrition."""
    return estimate_meal({"meal": meal})


@tool
def generate_grocery_list_tool(
    budget: str = "moderate",
    preferred_cuisine: str = "",
    days: int = 7,
) -> dict[str, Any]:
    """Generate a personalised grocery list grouped by category.
    ALWAYS call this when the user asks for a grocery or shopping list."""
    return generate_grocery_list({
        "budget": budget,
        "preferred_cuisine": preferred_cuisine,
        "days": days,
    })


@tool
def generate_recovery_advice_tool(
    sleep_hours: float = 0,
    soreness: str = "",
    energy: str = "",
) -> dict[str, Any]:
    """Generate personalised recovery advice based on recent check-ins and workouts.
    ALWAYS call this when the user asks about recovery, rest days, soreness, or sleep."""
    return generate_recovery_advice({
        "sleep_hours": sleep_hours if sleep_hours else None,
        "soreness": soreness,
        "energy": energy,
    })


@tool
def generate_weekly_report_tool() -> dict[str, Any]:
    """Generate a personalised weekly fitness and nutrition report.
    ALWAYS call this when the user asks for a weekly summary or report."""
    return generate_weekly_report({})


@tool
def generate_recipe_tool(
    recipe: str,
    servings: int = 2,
    dietary_preference: str = "",
    allergies: str = "",
) -> dict[str, Any]:
    """Generate a detailed recipe with ingredients, steps, and per-serving macros.
    ALWAYS call this when the user asks for a recipe or how to cook something."""
    return generate_recipe({
        "recipe": recipe,
        "servings": servings,
        "dietary_preference": dietary_preference,
        "allergies": allergies,
    })


@tool
def generate_motivation_tool(mood: str = "neutral") -> dict[str, Any]:
    """Generate a personalised motivational message based on the user's progress and mood.
    ALWAYS call this when the user seems demotivated, asks for encouragement, or requests motivation."""
    return generate_motivation({"mood": mood})


@tool
def fetch_exercises_tool(muscle_group: str) -> dict[str, Any]:
    """Fetch real exercises for a specific muscle group from the wger.de exercise database.
    Available muscle groups: chest, back, shoulders, upper arms, lower arms, abs, legs, calves, cardio.
    ALWAYS call this when the user asks for exercises for a specific muscle group or wants
    to know what exercises target a specific muscle."""
    return fetch_exercises_by_muscle({"muscle_group": muscle_group})


@tool
def enforce_dietary_restrictions_tool(meal: str) -> dict[str, Any]:
    """Check whether a meal violates the user's dietary restrictions or allergies.
    Call this before recommending a meal to a user with known dietary restrictions."""
    return enforce_dietary_restrictions({"meal": meal})


TOOLS = [
    calculate_calories_tool,
    hydration_tool,
    record_meal_tool,
    record_workout_tool,
    record_hydration_tool,
    record_checkin_tool,
    progress_tool,
    dashboard_tool,
    profile_tool,
    update_profile_tool,
    retrieve_knowledge_tool,
    check_goal_feasibility_tool,
    suggest_progressive_overload_tool,
    generate_meal_plan_tool,
    generate_workout_plan_tool,
    estimate_meal_tool,
    generate_grocery_list_tool,
    generate_recovery_advice_tool,
    generate_weekly_report_tool,
    generate_recipe_tool,
    generate_motivation_tool,
    enforce_dietary_restrictions_tool,
    fetch_exercises_tool,
]

SYSTEM_PROMPT = """You are FitAI, a fitness and nutrition assistant powered by Gemini.

Saved backend profile (fallback — frontend profile takes priority):
{profile}

════════════════════════════════════════════════════════════
MANDATORY TOOL RULES — you MUST follow every one, every time
════════════════════════════════════════════════════════════

0. The frontend profile in context is the SOURCE OF TRUTH.
   Never override it with the backend saved profile.

1. NEVER invent numbers. Every calorie, BMI, macro, or hydration
   figure MUST come from a tool result.

2. When the user mentions eating → ALWAYS call record_meal_tool.
   Estimate macros from nutrition knowledge, then log immediately.

3. When asked about calories / TDEE / BMI / macros → ALWAYS call
   calculate_calories_tool.

4. When asked about hydration → ALWAYS call hydration_tool.

5. When asked about progress or history → ALWAYS call progress_tool.

6. When the user mentions a workout → ALWAYS call record_workout_tool.

7. When asked for a meal plan → ALWAYS call generate_meal_plan_tool,
   then use the instruction_for_agent field to craft the response.

8. When asked for a workout plan → ALWAYS call generate_workout_plan_tool,
   then use the instruction_for_agent field to craft the response.

9. When asked to estimate a meal's nutrition → ALWAYS call
   estimate_meal_tool, then record it with record_meal_tool.

10. When asked for a grocery list → ALWAYS call generate_grocery_list_tool.

11. When asked about recovery, soreness, or rest → ALWAYS call
    generate_recovery_advice_tool.

12. When asked for a weekly report or summary → ALWAYS call
    generate_weekly_report_tool.

13. When asked for a recipe → ALWAYS call generate_recipe_tool.

14. When the user seems demotivated or asks for encouragement →
    ALWAYS call generate_motivation_tool.

15. When asked if a goal is realistic or achievable → ALWAYS call
    check_goal_feasibility_tool.

16. When asked how to progress an exercise → ALWAYS call
    suggest_progressive_overload_tool.

17. When a user with restrictions asks about a specific meal →
    call enforce_dietary_restrictions_tool first.

18. When the user asks for exercises targeting a specific muscle
    group → ALWAYS call fetch_exercises_tool to get real exercises
    from the database.

════════════════════════════════════════════════════════════
3-TIER KNOWLEDGE ROUTING
════════════════════════════════════════════════════════════

Tier 1 — Tools (numbers/data):
  Use tools for all calculations, logging, and personal data.

Tier 2 — RAG (stored knowledge):
  For educational questions, ALWAYS call retrieve_knowledge_tool first.
  - If found=true → use the returned context to answer.
  - If found=false → fall through to Tier 3.

Tier 3 — LLM knowledge:
  Answer from your own fitness/nutrition expertise.
  NEVER refuse to answer a fitness question — always provide
  a helpful response even if no tool or RAG result is available.

════════════════════════════════════════════════════════════
After every tool call, explain the result warmly and concisely.
For Type 2 tools (meal plan, workout plan, recipe, etc.) use the
instruction_for_agent value to generate the full structured answer.
════════════════════════════════════════════════════════════
"""


def _extract_reply(messages: list) -> str:
    for msg in reversed(messages):
        # Skip everything that is not an AI response
        if isinstance(msg, HumanMessage):
            continue
        if isinstance(msg, SystemMessage):
            continue
        if type(msg).__name__ == "ToolMessage":
            continue
        if type(msg).__name__ == "SystemMessage":
            continue

        content = getattr(msg, "content", "")

        # Gemini sometimes returns a list of parts
        if isinstance(content, list):
            parts = [
                p.get("text", "") if isinstance(p, dict) else str(p)
                for p in content
            ]
            content = " ".join(p for p in parts if p).strip()

        # Skip if content looks like a system prompt
        if content and "MANDATORY TOOL RULES" in content:
            continue
        if content and "STRICT RULES based on profile" in content:
            continue

        if content:
            return content

    return "I could not generate a response. Please try again."


class FitnessChat:
    def __init__(self):
        self.model = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash-lite",
            google_api_key=os.getenv("GEMINI_API_KEY"),
            temperature=0.1,
        )

        self.agent = create_react_agent(self.model, TOOLS)

        self.chat_history: list = []

    def send_message(self, message: str, context: dict[str, Any] | None = None) -> str:
        full_message = message
        profile_ctx: dict = {}
        if context:
            profile_ctx = context.get("profile") or {}
            full_message += "\n\nFrontend context:\n" + json.dumps(context, indent=2)[:3000]

        allergies    = profile_ctx.get("restrictions") or profile_ctx.get("allergies") or "none"
        disliked     = profile_ctx.get("dislikedFoods") or profile_ctx.get("disliked_foods") or "none"
        favorites    = profile_ctx.get("favoriteMeals") or profile_ctx.get("favorite_meals") or "none"
        cuisine      = profile_ctx.get("cuisine") or profile_ctx.get("preferred_cuisine") or "any"
        place        = profile_ctx.get("place") or profile_ctx.get("training_place") or "any"
        meals_per_day = profile_ctx.get("mealsPerDay") or profile_ctx.get("meals_per_day") or "3"

        profile_constraints = f"""STRICT RULES based on profile:
- Allergies/Restrictions: {allergies} — NEVER include these in any meal, plan, or grocery list under any circumstance. Do not suggest them even as alternatives.
- Disliked Foods: {disliked} — avoid these in all recommendations.
- Favorite Meals: {favorites} — prioritize these when relevant.
- Preferred Cuisine: {cuisine} — use this style when generating food recommendations.
- Training Place: {place} — tailor all workout plans to this location.
- Meals Per Day: {meals_per_day} — plan meal schedules accordingly.

These profile fields are ABSOLUTE constraints. Never contradict them or ask the user to clarify something already in their profile.

{profile_summary()}"""

        system_msg = SystemMessage(content=SYSTEM_PROMPT.format(profile=profile_constraints))
        result = self.agent.invoke({
            "messages": [system_msg] + self.chat_history + [HumanMessage(content=full_message)]
        })
        print(f"DEBUG result keys: {result.keys()}")
        print(f"DEBUG last message: {result['messages'][-1]}")
        print(f"DEBUG content: {result['messages'][-1].content}")
        reply = _extract_reply(result["messages"])

        self.chat_history.append(HumanMessage(content=message))
        self.chat_history.append(AIMessage(content=reply))
        if len(self.chat_history) > 40:
            self.chat_history = self.chat_history[-40:]
        return reply


def ask_gemini(prompt: str) -> str:
    chat = FitnessChat()
    return chat.send_message(prompt)
