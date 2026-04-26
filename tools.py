import json
import os
import re
from datetime import datetime, timedelta
from typing import Any

from memory import get_profile

LOG_FILES = {
    "meals": "meal_log.json",
    "workouts": "workout_log.json",
    "hydration": "hydration_log.json",
    "checkins": "checkin_log.json",
}

ACTIVITY_MULTIPLIERS = {
    "sedentary": 1.2,
    "light": 1.375,
    "lightly active": 1.375,
    "beginner": 1.375,
    "beginer": 1.375,
    "moderate": 1.55,
    "moderately active": 1.55,
    "active": 1.725,
    "very active": 1.9,
}

GOAL_CALORIE_ADJUSTMENTS = {
    "lose weight": -400,
    "fat loss": -400,
    "gain muscle": 300,
    "maintain": 0,
}


def _load_log(filename: str) -> list[dict[str, Any]]:
    if not os.path.exists(filename):
        return []
    try:
        with open(filename, "r", encoding="utf-8") as file:
            data = json.load(file)
    except (json.JSONDecodeError, OSError):
        return []
    return data if isinstance(data, list) else []


def _save_log(filename: str, entries: list[dict[str, Any]]) -> None:
    with open(filename, "w", encoding="utf-8") as file:
        json.dump(entries, file, indent=2)


def _number(value: Any, default: float | None = None) -> float | None:
    if value is None:
        return default
    match = re.search(r"-?\d+(?:\.\d+)?", str(value))
    return float(match.group()) if match else default


def _text(value: Any, default: str = "") -> str:
    return str(value or default).strip()


def _activity_multiplier(activity_level: str) -> float:
    normalized = _text(activity_level, "light").lower()
    return next(
        (multiplier for name, multiplier in ACTIVITY_MULTIPLIERS.items() if name in normalized),
        1.375,
    )


def _goal_adjustment(goal: str) -> int:
    normalized = _text(goal, "maintain").lower()
    return next(
        (adjustment for name, adjustment in GOAL_CALORIE_ADJUSTMENTS.items() if name in normalized),
        0,
    )


def _macro_targets(calories: int, weight_kg: float, goal: str) -> dict[str, int]:
    normalized = _text(goal, "maintain").lower()
    protein_per_kg = 2.0 if any(word in normalized for word in ["lose", "gain", "muscle"]) else 1.6
    protein_g = round(weight_kg * protein_per_kg)
    fat_g = round((calories * 0.27) / 9)
    carbs_g = round(max(calories - protein_g * 4 - fat_g * 9, 0) / 4)
    return {"protein_g": protein_g, "carbs_g": carbs_g, "fat_g": fat_g}


def _profile_from_input(data: dict[str, Any] | None = None) -> dict[str, Any]:
    data = data or {}
    profile = data.get("profile") if isinstance(data.get("profile"), dict) else data
    saved = get_profile()
    merged = {**saved, **profile}
    return {
        "age": merged.get("age"),
        "weight": merged.get("weight"),
        "height": merged.get("height"),
        "gender": merged.get("gender") or merged.get("sex"),
        "goal": merged.get("goal"),
        "fitness_level": merged.get("fitness_level") or merged.get("fitnessLevel"),
        "activity_level": merged.get("activity_level") or merged.get("activity"),
        "dietary_preference": merged.get("dietary_preference") or merged.get("restrictions"),
        "meals_per_day": merged.get("meals_per_day") or merged.get("mealsPerDay"),
        "training_place": merged.get("training_place") or merged.get("place"),
        "allergies": merged.get("allergies") or merged.get("restrictions"),
    }


def _recent_entries(filename: str, days: int) -> list[dict[str, Any]]:
    cutoff = datetime.now() - timedelta(days=days)
    recent = []
    for entry in _load_log(filename):
        raw_timestamp = entry.get("timestamp") or entry.get("date")
        try:
            if datetime.fromisoformat(str(raw_timestamp)) >= cutoff:
                recent.append(entry)
        except ValueError:
            continue
    return recent


def _bmi_category(bmi: float) -> str:
    categories = [
        (18.5, "underweight"),
        (25, "healthy weight"),
        (30, "overweight"),
        (float("inf"), "obesity range"),
    ]
    return next(label for limit, label in categories if bmi < limit)


def calculate_calories(data: dict[str, Any]) -> dict[str, Any]:
    profile = _profile_from_input(data)
    age = _number(profile.get("age"))
    weight_kg = _number(profile.get("weight"))
    height_cm = _number(profile.get("height"))
    missing = [
        field
        for field, value in {"age": age, "weight": weight_kg, "height": height_cm}.items()
        if value is None
    ]
    if missing:
        return {"ok": False, "missing_fields": missing}

    gender = _text(profile.get("gender"), "unknown").lower()
    gender_constants = {"male": 5, "man": 5, "m": 5, "female": -161, "woman": -161, "f": -161}
    sex_constant = gender_constants.get(gender, -78)
    bmr = round(10 * weight_kg + 6.25 * height_cm - 5 * age + sex_constant)
    tdee = round(bmr * _activity_multiplier(profile.get("activity_level")))
    goal = _text(profile.get("goal"), "maintain")
    calorie_target = max(round(tdee + _goal_adjustment(goal)), 1200)
    bmi = round(weight_kg / ((height_cm / 100) ** 2), 1)

    return {
        "ok": True,
        "bmr": bmr,
        "tdee": tdee,
        "maintenance_calories": tdee,
        "calorie_target": calorie_target,
        "bmi": bmi,
        "bmi_category": _bmi_category(bmi),
        "macros": _macro_targets(calorie_target, weight_kg, goal),
        "recommended_weekly_weight_change_percent": "0.25-1.0",
        "profile_used": profile,
    }


def calculate_hydration_needs(data: dict[str, Any]) -> dict[str, Any]:
    profile = _profile_from_input(data)
    weight_kg = _number(data.get("weight") or profile.get("weight"), 70) or 70
    activity = _text(data.get("activity_level") or profile.get("activity_level"), "light").lower()
    activity_bonus_map = {
        "sedentary": 0,
        "light": 250,
        "beginner": 250,
        "moderate": 500,
        "active": 750,
        "very active": 750,
    }
    bonus_ml = next((bonus for name, bonus in activity_bonus_map.items() if name in activity), 250)
    total_ml = round(weight_kg * 35 + bonus_ml)
    return {
        "ok": True,
        "water_ml": total_ml,
        "water_liters": round(total_ml / 1000, 2),
        "weight_kg": weight_kg,
        "activity_level": activity,
    }


def record_meal(data: dict[str, Any]) -> dict[str, Any]:
    entry = {
        "meal": data.get("meal") or data.get("description"),
        "calories": int(_number(data.get("calories"), 0) or 0),
        "protein_g": int(_number(data.get("protein_g") or data.get("protein"), 0) or 0),
        "carbs_g": int(_number(data.get("carbs_g") or data.get("carbs"), 0) or 0),
        "fat_g": int(_number(data.get("fat_g") or data.get("fat"), 0) or 0),
        "timestamp": data.get("timestamp") or datetime.now().isoformat(),
    }
    entries = _load_log(LOG_FILES["meals"])
    entries.append(entry)
    _save_log(LOG_FILES["meals"], entries)
    return {"ok": True, "entry": entry, "total_entries": len(entries)}


def record_workout(data: dict[str, Any]) -> dict[str, Any]:
    entry = {
        "session": data.get("session") or data.get("workout"),
        "duration_minutes": int(_number(data.get("duration_minutes"), 0) or 0),
        "difficulty_rating": data.get("difficulty_rating"),
        "completed": bool(data.get("completed", True)),
        "timestamp": data.get("timestamp") or datetime.now().isoformat(),
    }
    entries = _load_log(LOG_FILES["workouts"])
    entries.append(entry)
    _save_log(LOG_FILES["workouts"], entries)
    return {"ok": True, "entry": entry, "total_entries": len(entries)}


def record_hydration(data: dict[str, Any]) -> dict[str, Any]:
    today = datetime.now().date().isoformat()
    entry = {
        "date": data.get("date") or today,
        "ml": int(_number(data.get("ml"), 0) or 0),
        "timestamp": data.get("timestamp") or datetime.now().isoformat(),
    }
    entries = _load_log(LOG_FILES["hydration"])
    entries.append(entry)
    _save_log(LOG_FILES["hydration"], entries)
    daily_total = sum(int(item.get("ml", 0)) for item in entries if item.get("date") == entry["date"])
    return {"ok": True, "entry": entry, "daily_total_ml": daily_total}


def record_checkin(data: dict[str, Any]) -> dict[str, Any]:
    entry = {
        "sleep_hours": _number(data.get("sleep_hours")),
        "mood": data.get("mood"),
        "soreness": data.get("soreness"),
        "energy": data.get("energy"),
        "weight": _number(data.get("weight")),
        "timestamp": data.get("timestamp") or datetime.now().isoformat(),
    }
    entries = _load_log(LOG_FILES["checkins"])
    entries.append(entry)
    _save_log(LOG_FILES["checkins"], entries)
    return {"ok": True, "entry": entry, "total_entries": len(entries)}


def get_progress_data(data: dict[str, Any] | None = None) -> dict[str, Any]:
    data = data or {}
    days = int(_number(data.get("days"), 7) or 7)
    meals = _recent_entries(LOG_FILES["meals"], days)
    workouts = _recent_entries(LOG_FILES["workouts"], days)
    hydration = _recent_entries(LOG_FILES["hydration"], days)
    checkins = _recent_entries(LOG_FILES["checkins"], days)
    total_calories = sum(int(entry.get("calories", 0)) for entry in meals)
    total_protein = sum(int(entry.get("protein_g", 0)) for entry in meals)
    workout_days = sorted({entry.get("timestamp", "")[:10] for entry in workouts if entry.get("timestamp")})
    hydration_ml = sum(int(entry.get("ml", 0)) for entry in hydration)
    return {
        "ok": True,
        "days": days,
        "workouts_completed": len(workouts),
        "workout_days": workout_days,
        "meals_logged": len(meals),
        "calories_logged": total_calories,
        "protein_logged_g": total_protein,
        "hydration_logged_ml": hydration_ml,
        "checkins_logged": len(checkins),
        "streak_days": calculate_streak({}),
    }


def calculate_streak(data: dict[str, Any] | None = None) -> int:
    workouts = _load_log(LOG_FILES["workouts"])
    completed_dates = {
        entry.get("timestamp", "")[:10]
        for entry in workouts
        if entry.get("completed") and entry.get("timestamp")
    }
    streak = 0
    current = datetime.now().date()
    while current.isoformat() in completed_dates:
        streak += 1
        current -= timedelta(days=1)
    return streak


def get_dashboard_data(data: dict[str, Any] | None = None) -> dict[str, Any]:
    metrics = calculate_calories(data or {"profile": get_profile()})
    progress = get_progress_data({"days": 7})
    return {
        "bmi": metrics.get("bmi", "n/a"),
        "calorie_target": metrics.get("calorie_target", "n/a"),
        "protein_target": metrics.get("macros", {}).get("protein_g", "n/a"),
        "workouts_completed": progress["workouts_completed"],
        "streak": progress["streak_days"],
        "meals_logged": progress["meals_logged"],
        "progress": progress,
    }


def get_profile_data(data: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"ok": True, "profile": _profile_from_input(data)}
