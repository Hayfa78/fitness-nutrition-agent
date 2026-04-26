import json
import mimetypes
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

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

APP_DIR = Path(__file__).resolve().parent
PROJECT_DIR = APP_DIR.parent
sys.path.insert(0, str(PROJECT_DIR))

from dotenv import load_dotenv
from langchain_core.messages import AIMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from agent import FitnessChat

load_dotenv(PROJECT_DIR / ".env")

MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite")
API_KEY = os.getenv("GEMINI_API_KEY")


def friendly_error(exc):
    text = str(exc)
    lower = text.lower()
    if "resource_exhausted" in lower or "quota" in lower or "429" in lower:
        return {
            "status": 429,
            "error": "FitAI reached the Gemini request limit. Please wait a minute and try again.",
        }
    if "10061" in lower or "connection refused" in lower or "failed to connect" in lower:
        return {
            "status": 503,
            "error": "Coach is temporarily unavailable. Please try again.",
        }
    if "api_key" in lower or "api key" in lower:
        return {
            "status": 401,
            "error": "The backend API key is missing or invalid. Check your environment variables.",
        }
    return {
        "status": 500,
        "error": "Coach is temporarily unavailable. Please try again.",
    }


def json_response(handler, payload, status=200):
    body = json.dumps(payload).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def build_prompt(message, profile, logs):
    return f"""You are FitAI, a careful fitness and nutrition AI assistant.

Use the user's profile and localStorage logs to answer personally.
Always consider these context fields when present:
- goal
- fitness level
- training place
- allergies or dietary restrictions
- last workout
- meals logged today
- preferred workout time
- disliked foods
- favorite meals
- preferred cuisine
- equipment available

Do not pretend to be a doctor. Give safe, practical advice.
If the user describes dangerous behavior, extreme weight loss, training through pain,
overtraining, very low calories, or poor recovery, warn them and suggest a safer alternative.

User profile:
{json.dumps(profile, indent=2)}

Recent local logs:
{json.dumps(logs, indent=2)[:6000]}

User message:
{message}

Answer as FitAI in a clear, helpful way. Keep it structured but not too long."""


def ask_llm(message, profile, logs):
    if not API_KEY:
        return "The backend API key is missing. Add GEMINI_API_KEY to your environment and restart the server."

    chat = FitnessChat()
    messages = chat.send_message(message, {"profile": profile, "logs": logs})
    for msg in reversed(messages):
        content = getattr(msg, "content", "")
        if isinstance(msg, AIMessage) and content:
            return content if isinstance(content, str) else str(content)
    return "I could not generate a response."


def build_tool_prompt(tool, profile, logs):
    common = f"""You are FitAI, an AI fitness and nutrition coach.

Personalize everything using this full user profile and localStorage history.

Profile:
{json.dumps(profile, indent=2)}

Logs and context:
{json.dumps(logs, indent=2)[:6000]}

Safety rules:
- Avoid extreme calorie deficits.
- Warn against training through pain.
- Recommend recovery when sleep, soreness, or energy are poor.
- Respect allergies, disliked foods, preferred cuisine, favorite meals, available equipment, training place, and preferred workout time.
"""
    prompts = {
        "calories": """
Generate personalized calorie and macro targets.
Include BMI, BMR, TDEE, goal calories, protein, carbs, fat, and a short explanation.
Use clear headings and concise bullet points.
""",
        "workout": """
Generate a personalized weekly workout plan.
Use the user's goal, fitness level, training place, equipment, recovery, and last workout.

Return ONLY valid JSON in this exact shape:
{
  "summary": "short personalized summary",
  "days_per_week": 3,
  "difficulty": "beginner",
  "progression": "simple progression instruction",
  "exercises": [
    {"name": "Exercise name", "sets": 3, "reps": "10-12", "rest": "60 sec"}
  ]
}
""",
        "meal_plan": """
Generate a personalized daily meal plan based on calorie goal, allergies/restrictions,
disliked foods, favorite meals, preferred cuisine, and budget.
Return ONLY valid JSON in this exact shape:
{
  "summary": "short personalized summary",
  "meals": [
    {"name": "Breakfast", "food": "meal name", "calories": 450, "protein": 35, "carbs": 50, "fat": 12}
  ],
  "notes": "short practical notes"
}
""",
        "meal_estimate": """
Estimate the calories and macros for the meal in logs.meal_to_estimate.
Use the user's profile and preferences only for context. Do not avoid the food unless it conflicts with allergies.
Return ONLY valid JSON in this exact shape:
{
  "meal": "meal name",
  "calories": 450,
  "protein": 25,
  "carbs": 55,
  "fat": 14,
  "note": "short practical note"
}
""",
        "hydration": """
Generate a personalized hydration target based on body weight, activity level, training place, and weather/activity assumptions.
Include a practical drinking schedule.
""",
        "groceries": """
Generate a grocery list for the user's goal and preferences.
Avoid disliked foods and allergies. Favor preferred cuisine and budget.
""",
        "recovery": """
Generate a sleep and recovery recommendation from the user's latest check-in, soreness, energy, and workout history.
""",
        "weekly_report": """
Generate a personalized weekly fitness report.
Include:
- short summary
- stats overview
- what went well
- what needs adjustment
- next week recommendation
- next week workout and nutrition focus

Use natural progress language, for example:
"You completed 2/3 workouts this week. One more would keep you on track."

Keep it clear, supportive, and personalized.
""",
    }
    return common + prompts.get(tool, "\nGenerate a helpful personalized response for this tool.")


def ask_tool(tool, profile, logs):
    if not API_KEY:
        return {"reply": "The backend API key is missing. Add GEMINI_API_KEY to your environment and restart the server."}

    llm = ChatGoogleGenerativeAI(
        model=MODEL_NAME,
        google_api_key=API_KEY,
        temperature=0.25,
    )
    text = llm.invoke(build_tool_prompt(tool, profile, logs)).content.strip()

    if tool in {"workout", "meal_plan", "meal_estimate"}:
        try:
            clean = text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
            return {"reply": text, "data": json.loads(clean)}
        except Exception:
            return {"reply": text, "data": None}

    return {"reply": text}


class FitAIHandler(BaseHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(204)
        self.end_headers()

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path == "/health":
            json_response(self, {"ok": True, "service": "FitAI API"})
            return

        if path == "/":
            path = "/index.html"

        file_path = (APP_DIR / path.lstrip("/")).resolve()
        if not str(file_path).startswith(str(APP_DIR)) or not file_path.exists() or file_path.is_dir():
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"Not found")
            return

        content_type = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.end_headers()
        self.wfile.write(file_path.read_bytes())

    def do_POST(self):
        if self.path not in {"/api/chat", "/chat", "/api/tool", "/tool"}:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"Not found")
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
            data = json.loads(self.rfile.read(length).decode("utf-8"))
            if self.path in {"/api/tool", "/tool"}:
                result = ask_tool(
                    data.get("tool", ""),
                    data.get("profile", {}),
                    data.get("logs", {}),
                )
            else:
                result = {
                    "reply": ask_llm(
                        data.get("message", ""),
                        data.get("profile", {}),
                        data.get("logs", {}),
                    )
                }
            json_response(self, result)
        except Exception as exc:
            error = friendly_error(exc)
            json_response(self, {"error": error["error"]}, error["status"])


if __name__ == "__main__":
    port = int(os.getenv("PORT", os.getenv("FITAI_PORT", "8504")))
    server = ThreadingHTTPServer(("0.0.0.0", port), FitAIHandler)
    print(f"FitAI API running at http://127.0.0.1:{port}")
    print("Your API key stays in .env and is not sent to the browser.")
    server.serve_forever()
