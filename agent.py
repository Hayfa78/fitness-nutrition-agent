import json
import os
from typing import Any

for proxy_name in (
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "ALL_PROXY",
    "http_proxy",
    "https_proxy",
    "all_proxy",
):
    os.environ.pop(proxy_name, None)
os.environ["NO_PROXY"] = "localhost,127.0.0.1,::1"
os.environ["no_proxy"] = "localhost,127.0.0.1,::1"

from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain.tools import tool
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from memory import get_profile, profile_summary, update_profile
from rag import retrieve_context
from tools import (
    calculate_calories,
    calculate_hydration_needs,
    get_dashboard_data,
    get_profile_data,
    get_progress_data,
    record_checkin,
    record_hydration,
    record_meal,
    record_workout,
)

load_dotenv(dotenv_path=".env")


@tool
def calculate_calories_tool(profile: dict[str, Any]) -> dict[str, Any]:
    """Calculate BMI, BMR, TDEE, calorie target, macros, and weekly change target from a structured profile."""
    return calculate_calories({"profile": profile})


@tool
def hydration_tool(profile: dict[str, Any]) -> dict[str, Any]:
    """Calculate daily hydration target from structured profile data."""
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
    """Save a meal entry after Gemini estimates its calories and macros."""
    return record_meal(
        {
            "meal": meal,
            "calories": calories,
            "protein_g": protein_g,
            "carbs_g": carbs_g,
            "fat_g": fat_g,
            "timestamp": timestamp,
        }
    )


@tool
def record_workout_tool(
    session: str,
    duration_minutes: int = 0,
    difficulty_rating: str = "",
    completed: bool = True,
    timestamp: str = "",
) -> dict[str, Any]:
    """Save a completed workout entry from structured workout data."""
    return record_workout(
        {
            "session": session,
            "duration_minutes": duration_minutes,
            "difficulty_rating": difficulty_rating,
            "completed": completed,
            "timestamp": timestamp,
        }
    )


@tool
def record_hydration_tool(ml: int, timestamp: str = "") -> dict[str, Any]:
    """Save water intake in millilitres."""
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
    """Save a daily check-in with sleep, mood, soreness, energy, and optional weight."""
    return record_checkin(
        {
            "sleep_hours": sleep_hours,
            "mood": mood,
            "soreness": soreness,
            "energy": energy,
            "weight": weight,
            "timestamp": timestamp,
        }
    )


@tool
def progress_tool(days: int = 7) -> dict[str, Any]:
    """Return structured meal, workout, hydration, check-in, and streak progress data."""
    return get_progress_data({"days": days})


@tool
def dashboard_tool(profile: dict[str, Any]) -> dict[str, Any]:
    """Return structured dashboard values for BMI, calories, protein, workouts, streak, and progress."""
    return get_dashboard_data({"profile": profile})


@tool
def profile_tool() -> dict[str, Any]:
    """Return the saved user profile as structured JSON."""
    return get_profile_data({})


@tool
def update_profile_tool(field: str, value: str) -> dict[str, Any]:
    """Update one saved profile field. Valid fields are controlled by memory.py."""
    before = get_profile().copy()
    update_profile(field, value)
    after = get_profile().copy()
    return {"ok": before != after, "field": field, "value": value, "profile": after}


@tool
def retrieve_knowledge_tool(query: str) -> dict[str, Any]:
    """Retrieve local fitness and nutrition knowledge snippets for Gemini to use in its response."""
    return {"ok": True, "context": retrieve_context(query)}


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
]

SYSTEM_PROMPT = """You are FitAI, a Gemini-powered fitness and nutrition agent.

Architecture:
- You decide whether a tool is needed.
- Python does not route user intent for you.
- Tools only return JSON data.
- After a tool result, explain it naturally and personally.

Use the saved profile and conversation context when helpful:
{profile}

Important behavior:
- For calorie, macro, BMI, hydration, dashboard, progress, profile, or logging needs, call the matching tool.
- For meal logging, estimate calories/macros yourself, then call record_meal_tool with those numbers.
- For meal calorie questions that are not logging requests, estimate the food yourself and answer normally.
- Use retrieve_knowledge_tool only for broad educational questions, not for specific food calorie estimates.
- For workout and meal-plan creation, you may generate the plan yourself using the profile, because that is creative coaching rather than a calculator.
- For safety concerns, explain safer alternatives directly and recommend professional help for medical, eating-disorder, injury, or dangerous symptoms.
- Do not expose API keys or backend internals.
- Keep answers clear, supportive, and concise.
"""


class FitnessChat:
    def __init__(self):
        model = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash-lite",
            google_api_key=os.getenv("GEMINI_API_KEY"),
            temperature=0.25,
        )
        self.agent = create_agent(
            model=model,
            tools=TOOLS,
            system_prompt=SYSTEM_PROMPT.format(profile=profile_summary()),
        )
        self.messages = []

    def send_message(self, message: str, context: dict[str, Any] | None = None) -> list:
        context_text = ""
        if context:
            context_text = "\nFrontend context:\n" + json.dumps(context, indent=2)[:6000]
        prompt = SYSTEM_PROMPT.format(profile=profile_summary()) + context_text
        input_messages = [SystemMessage(content=prompt), *self.messages, HumanMessage(content=message)]
        result = self.agent.invoke({"messages": input_messages})
        result_messages = result["messages"]
        self.messages = [
            msg
            for msg in result_messages
            if not isinstance(msg, SystemMessage)
        ]
        return result_messages[len(input_messages):]


def _last_text(messages: list[Any]) -> str:
    for message in reversed(messages):
        if isinstance(message, AIMessage) and message.content:
            return message.content if isinstance(message.content, str) else str(message.content)
    return ""


def ask_gemini(prompt: str) -> str:
    chat = FitnessChat()
    return _last_text(chat.send_message(prompt))
