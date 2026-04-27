import json
import os
import random
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


# ── Type 1: pure math/rule-based ─────────────────────────────────────────────

def check_goal_feasibility(data: dict[str, Any]) -> dict[str, Any]:
    profile = _profile_from_input(data)
    weight_kg = _number(data.get("current_weight") or profile.get("weight"))
    target_weight_kg = _number(data.get("target_weight"))
    timeframe_weeks = _number(data.get("timeframe_weeks"), 12) or 12
    goal = _text(data.get("goal") or profile.get("goal"), "maintain")

    if weight_kg is None:
        return {"ok": False, "missing_fields": ["current_weight or profile weight"]}

    if target_weight_kg is None:
        return {
            "ok": True,
            "feasible": True,
            "message": f"No weight target provided. Goal is: {goal}.",
            "recommendation": "Track progress weekly and adjust calorie intake accordingly.",
        }

    weight_change_kg = target_weight_kg - weight_kg
    weekly_change_kg = weight_change_kg / timeframe_weeks

    if weight_change_kg < 0:
        feasible = abs(weekly_change_kg) <= 0.75
        safe_weeks = round(abs(weight_change_kg) / 0.5)
        category = "weight loss"
    elif weight_change_kg > 0:
        feasible = weekly_change_kg <= 0.25
        safe_weeks = round(abs(weight_change_kg) / 0.2)
        category = "muscle gain"
    else:
        return {"ok": True, "feasible": True, "message": "Target weight equals current weight — maintenance goal."}

    return {
        "ok": True,
        "feasible": feasible,
        "category": category,
        "current_weight_kg": weight_kg,
        "target_weight_kg": target_weight_kg,
        "weight_change_kg": round(weight_change_kg, 1),
        "timeframe_weeks": int(timeframe_weeks),
        "weekly_change_kg": round(weekly_change_kg, 2),
        "recommended_weeks": safe_weeks if not feasible else int(timeframe_weeks),
        "message": (
            f"Goal is achievable and safe within {int(timeframe_weeks)} weeks." if feasible
            else f"Timeline too aggressive for safe {category}. Aim for {safe_weeks} weeks instead."
        ),
    }


def suggest_progressive_overload(data: dict[str, Any]) -> dict[str, Any]:
    profile = _profile_from_input(data)
    exercise = _text(data.get("exercise") or data.get("exercise_name"), "exercise")
    current_weight_kg = _number(data.get("weight_kg") or data.get("load_kg"))
    current_reps = int(_number(data.get("reps") or data.get("current_reps"), 10) or 10)
    current_sets = int(_number(data.get("sets") or data.get("current_sets"), 3) or 3)
    weeks_at_current = int(_number(data.get("weeks_at_current"), 1) or 1)
    fitness_level = _text(
        data.get("fitness_level") or profile.get("fitness_level"), "intermediate"
    ).lower()

    progression_interval = 2 if "begin" in fitness_level else 1
    should_progress = weeks_at_current >= progression_interval

    next_reps = current_reps + 1 if should_progress else current_reps
    next_weight_kg = (
        round(current_weight_kg * 1.05, 1)
        if (current_weight_kg and current_reps >= 12 and should_progress)
        else current_weight_kg
    )
    next_sets = (
        current_sets + 1
        if (should_progress and current_reps >= 15 and current_sets < 5)
        else current_sets
    )

    suggestions = []
    if should_progress:
        if current_weight_kg and current_reps >= 12:
            suggestions.append(f"Increase load: {current_weight_kg} kg → {next_weight_kg} kg (~5%)")
        else:
            suggestions.append(f"Add a rep per set: {current_reps} → {next_reps}")
        if current_sets < 5 and current_reps >= 15:
            suggestions.append(f"Add a set: {current_sets} → {next_sets}")
    else:
        weeks_left = progression_interval - weeks_at_current
        suggestions.append(f"Hold current load for {weeks_left} more week(s) before progressing.")

    return {
        "ok": True,
        "exercise": exercise,
        "should_progress": should_progress,
        "current": {"sets": current_sets, "reps": current_reps, "weight_kg": current_weight_kg},
        "next": {"sets": next_sets, "reps": next_reps, "weight_kg": next_weight_kg},
        "suggestions": suggestions,
        "principle": "Increase weight ~5% or add 1-2 reps every 1-2 weeks to drive continued adaptation.",
    }


# ── Meal option pools for variety on each regeneration ───────────────────────

_BREAKFAST_OPTIONS = [
    "Overnight oats with banana and almond butter",
    "Scrambled eggs with spinach and whole-wheat toast",
    "Greek yogurt parfait with granola and mixed berries",
    "Smoothie bowl with protein powder, frozen berries, and chia seeds",
    "Avocado toast with poached eggs and cherry tomatoes",
    "Whole-grain pancakes with fresh fruit and a drizzle of honey",
    "Protein omelette with mushrooms, onions, and feta",
    "Chia pudding with coconut milk, mango, and almonds",
    "Cottage cheese bowl with pineapple and sunflower seeds",
    "High-protein French toast with cinnamon and strawberries",
]

_LUNCH_OPTIONS = [
    "Grilled chicken salad with quinoa, cucumber, and lemon-herb dressing",
    "Lentil soup with whole-grain bread and a side salad",
    "Tuna wrap with lettuce, tomato, and hummus",
    "Brown rice bowl with roasted vegetables and chickpeas",
    "Turkey and avocado sandwich on whole-grain bread",
    "Grilled salmon with sweet potato and steamed broccoli",
    "Falafel wrap with tabbouleh and tahini sauce",
    "Chicken and vegetable stir-fry with brown rice",
    "Black bean burrito bowl with salsa, lime rice, and Greek yogurt",
    "Egg and vegetable frittata with a green side salad",
]

_DINNER_OPTIONS = [
    "Baked salmon with roasted asparagus and quinoa",
    "Lean beef stir-fry with mixed vegetables and brown rice",
    "Grilled chicken breast with sweet potato mash and green beans",
    "Lentil and vegetable curry with basmati rice",
    "Baked cod with roasted root vegetables and couscous",
    "Turkey meatballs with zucchini noodles and marinara sauce",
    "Stuffed bell peppers with ground turkey and black beans",
    "Sheet-pan chicken thighs with roasted cauliflower and chickpeas",
    "Shrimp and vegetable skewers with wild rice",
    "Tofu and broccoli stir-fry with ginger-soy sauce and brown rice",
]

_SNACK_OPTIONS = [
    "Greek yogurt with honey and walnuts (approx. 200 kcal)",
    "Apple slices with almond butter (approx. 180 kcal)",
    "Protein shake blended with a banana (approx. 220 kcal)",
    "Hummus with carrot sticks and whole-grain crackers (approx. 200 kcal)",
    "Cottage cheese with pineapple chunks (approx. 170 kcal)",
    "Rice cakes with peanut butter and banana slices (approx. 210 kcal)",
    "A handful of mixed nuts and dried fruit (approx. 180 kcal)",
    "Hard-boiled eggs with cherry tomatoes (approx. 160 kcal)",
    "Celery sticks with peanut butter and raisins (approx. 190 kcal)",
    "Edamame with sea salt (approx. 150 kcal)",
]


# ── Type 2: context collectors (no LLM calls, return instruction_for_agent) ──

def generate_meal_plan(data: dict[str, Any]) -> dict[str, Any]:
    profile = _profile_from_input(data)
    cal_data = calculate_calories({"profile": profile})
    calorie_target = cal_data.get("calorie_target", "unknown")
    macros = cal_data.get("macros", {})
    meals_per_day = int(_number(profile.get("meals_per_day"), 3) or 3)
    goal = _text(profile.get("goal"), "maintain")
    dietary = _text(profile.get("dietary_preference") or data.get("dietary_preference") or data.get("restrictions"), "none")
    allergies = _text(profile.get("allergies") or data.get("allergies") or data.get("restrictions"), "none")
    disliked = _text(data.get("dislikedFoods") or data.get("disliked_foods") or profile.get("disliked_foods"), "none")
    favorites = _text(data.get("favoriteMeals") or data.get("favorite_meals") or profile.get("favorite_meals"), "none")
    cuisine = _text(data.get("preferred_cuisine") or data.get("cuisine"), "any")

    banned = ", ".join(
        item.strip() for item in
        set((allergies + "," + disliked).replace("none", "").split(","))
        if item.strip()
    ) or "none"

    # Random meal starters — different pool pick every call guarantees variety
    breakfast_hint = random.choice(_BREAKFAST_OPTIONS)
    lunch_hint     = random.choice(_LUNCH_OPTIONS)
    dinner_hint    = random.choice(_DINNER_OPTIONS)
    snack_hint     = random.choice(_SNACK_OPTIONS)
    variation_seed = random.randint(1000, 9999)

    try:
        snack_calories = round(int(calorie_target) * 0.10)
    except (ValueError, TypeError):
        snack_calories = 200

    return {
        "ok": True,
        "instruction_for_agent": (
            f"[Variation #{variation_seed}] "
            f"Create a personalized daily meal plan targeting {calorie_target} kcal. "
            f"Macros: {macros.get('protein_g','?')}g protein, {macros.get('carbs_g','?')}g carbs, "
            f"{macros.get('fat_g','?')}g fat. Goal: {goal}. "
            f"Dietary preference: {dietary}. Preferred cuisine: {cuisine}. "
            f"Favorite meals to prioritize: {favorites}. "
            f"ABSOLUTE EXCLUSIONS — NEVER include these in any meal, ingredient, or alternative: {banned}. "
            "Do not mention banned items even as substitutes. "
            "Use these as inspiration for each slot (adapt ingredients to respect all dietary rules and exclusions above): "
            f"Breakfast inspiration: {breakfast_hint}. "
            f"Lunch inspiration: {lunch_hint}. "
            f"Dinner inspiration: {dinner_hint}. "
            f"Snack inspiration: {snack_hint}. "
            "IMPORTANT: The meals array MUST contain exactly 4 items in this order: Breakfast, Lunch, Dinner, Snack. "
            f"The snack must use approximately {snack_calories} kcal "
            "(the remaining calories after breakfast, lunch, and dinner add up to the daily target). "
            "Never return an empty snack, a placeholder, or a snack named 'Plan snack'. "
            "Generate a specific, real snack food that fits the goal and dietary preference. "
            "Return ONLY valid JSON with no markdown: "
            "{\"summary\": \"...\", \"meals\": [{\"name\": \"Breakfast\", \"food\": \"...\", "
            "\"calories\": 0, \"protein\": 0, \"carbs\": 0, \"fat\": 0}, "
            "{\"name\": \"Lunch\", \"food\": \"...\", \"calories\": 0, \"protein\": 0, \"carbs\": 0, \"fat\": 0}, "
            "{\"name\": \"Dinner\", \"food\": \"...\", \"calories\": 0, \"protein\": 0, \"carbs\": 0, \"fat\": 0}, "
            "{\"name\": \"Snack\", \"food\": \"...\", \"calories\": 0, \"protein\": 0, \"carbs\": 0, \"fat\": 0}], "
            "\"notes\": \"...\"}"
        ),
        "context": {
            "calorie_target": calorie_target,
            "macros": macros,
            "meals_per_day": meals_per_day,
            "goal": goal,
            "dietary_preference": dietary,
            "allergies": allergies,
            "disliked_foods": disliked,
            "favorite_meals": favorites,
            "preferred_cuisine": cuisine,
            "banned_ingredients": banned,
        },
    }


def generate_workout_plan(data: dict[str, Any]) -> dict[str, Any]:
    profile = _profile_from_input(data)
    goal = _text(profile.get("goal") or data.get("goal"), "general fitness")
    fitness_level = _text(profile.get("fitness_level") or data.get("fitness_level"), "beginner")
    training_place = _text(profile.get("training_place") or data.get("training_place"), "home")
    days_per_week = int(_number(data.get("days_per_week"), 3) or 3)
    equipment = _text(data.get("equipment") or data.get("available_equipment"), "bodyweight only")
    return {
        "ok": True,
        "instruction_for_agent": (
            f"Create a personalized {days_per_week}-day/week workout plan for a {fitness_level} "
            f"training at {training_place} with {equipment}. Goal: {goal}. "
            "Include warm-up, main exercises with sets/reps/rest, and cool-down. "
            "IMPORTANT: every object in the exercises array MUST have a 'name' key with the exercise name as a string. "
            "Return ONLY valid JSON in exactly this shape, no markdown, no extra text:\n"
            "{\"summary\": \"short summary\", \"days_per_week\": 3, \"difficulty\": \"beginner\", "
            "\"progression\": \"progression tip\", "
            "\"exercises\": [{\"name\": \"Push-ups\", \"sets\": 3, \"reps\": \"10-12\", \"rest\": \"60 sec\"}]}"
        ),
        "context": {
            "goal": goal,
            "fitness_level": fitness_level,
            "training_place": training_place,
            "days_per_week": days_per_week,
            "equipment": equipment,
        },
    }


def estimate_meal(data: dict[str, Any]) -> dict[str, Any]:
    meal_text = _text(
        data.get("meal") or data.get("meal_to_estimate") or data.get("food"), ""
    )
    if not meal_text:
        return {"ok": False, "message": "No meal description provided."}
    profile = _profile_from_input(data)
    goal = _text(profile.get("goal"), "maintain")
    return {
        "ok": True,
        "meal": meal_text,
        "instruction_for_agent": (
            f"Estimate the calories and macros for: '{meal_text}'. "
            f"User goal: {goal}. Use standard serving sizes. "
            "Return JSON: {\"meal\": \"...\", \"calories\": 0, \"protein\": 0, \"carbs\": 0, \"fat\": 0, \"note\": \"...\"}"
        ),
    }


def generate_grocery_list(data: dict[str, Any]) -> dict[str, Any]:
    profile = _profile_from_input(data)
    goal = _text(profile.get("goal"), "maintain")
    dietary = _text(profile.get("dietary_preference") or data.get("restrictions"), "none")
    allergies = _text(profile.get("allergies") or data.get("restrictions"), "none")
    disliked = _text(data.get("dislikedFoods") or data.get("disliked_foods") or profile.get("disliked_foods"), "none")
    favorites = _text(data.get("favoriteMeals") or data.get("favorite_meals") or profile.get("favorite_meals"), "none")
    budget = _text(data.get("budget"), "moderate")
    cuisine = _text(data.get("preferred_cuisine") or data.get("cuisine"), "any")
    days = int(_number(data.get("days"), 7) or 7)

    banned = ", ".join(
        item.strip() for item in
        set((allergies + "," + disliked).replace("none", "").split(","))
        if item.strip()
    ) or "none"

    return {
        "ok": True,
        "instruction_for_agent": (
            f"Generate a {days}-day grocery list for goal: {goal}. "
            f"Dietary preference: {dietary}. Budget: {budget}. Preferred cuisine: {cuisine}. "
            f"Prioritize ingredients for these favorite meals: {favorites}. "
            f"ABSOLUTE EXCLUSIONS — NEVER include these ingredients or any product containing them: {banned}. "
            "Do not list banned items under any category, even as alternatives. "
            "Group items by category: Proteins, Vegetables, Grains, Dairy/Alternatives, Extras. "
            "Keep it practical and minimise waste."
        ),
        "context": {
            "goal": goal,
            "dietary_preference": dietary,
            "allergies": allergies,
            "disliked_foods": disliked,
            "favorite_meals": favorites,
            "budget": budget,
            "days": days,
            "banned_ingredients": banned,
        },
    }


def generate_recovery_advice(data: dict[str, Any]) -> dict[str, Any]:
    checkins = _recent_entries(LOG_FILES["checkins"], 7)
    workouts = _recent_entries(LOG_FILES["workouts"], 7)
    latest = checkins[-1] if checkins else {}
    sleep_hours = _number(latest.get("sleep_hours") or data.get("sleep_hours"), 7)
    soreness = _text(latest.get("soreness") or data.get("soreness"), "unknown")
    energy = _text(latest.get("energy") or data.get("energy"), "unknown")
    workouts_this_week = len(workouts)
    return {
        "ok": True,
        "instruction_for_agent": (
            f"Generate personalised recovery advice. "
            f"Sleep: {sleep_hours}h, Soreness: {soreness}, Energy: {energy}, "
            f"Workouts this week: {workouts_this_week}. "
            "Cover sleep optimisation, active recovery, soreness management, and rest-day activities. "
            "Be specific and practical."
        ),
        "context": {
            "sleep_hours": sleep_hours,
            "soreness": soreness,
            "energy": energy,
            "workouts_this_week": workouts_this_week,
            "recent_checkins": checkins[-3:] if checkins else [],
        },
    }


def generate_weekly_report(data: dict[str, Any]) -> dict[str, Any]:
    progress = get_progress_data({"days": 7})
    profile = _profile_from_input(data)
    goal = _text(profile.get("goal"), "general fitness")
    cal_data = calculate_calories({"profile": profile})
    calorie_target = cal_data.get("calorie_target", "unknown")
    return {
        "ok": True,
        "instruction_for_agent": (
            f"Generate a supportive weekly fitness report. Goal: {goal}. "
            f"Calorie target: {calorie_target} kcal/day. "
            f"This week: {progress['workouts_completed']} workouts, "
            f"{progress['meals_logged']} meals logged, "
            f"{progress['calories_logged']} kcal consumed, "
            f"{progress['protein_logged_g']}g protein, "
            f"{progress['hydration_logged_ml']}ml water, "
            f"streak: {progress['streak_days']} days. "
            "Include: summary, what went well, areas to improve, next-week recommendation. "
            "Be warm, specific, and motivating."
        ),
        "context": progress,
    }


def generate_recipe(data: dict[str, Any]) -> dict[str, Any]:
    profile = _profile_from_input(data)
    recipe_name = _text(
        data.get("recipe") or data.get("dish") or data.get("food"), "a healthy high-protein meal"
    )
    dietary = _text(profile.get("dietary_preference") or data.get("dietary_preference"), "none")
    allergies = _text(profile.get("allergies") or data.get("allergies"), "none")
    servings = int(_number(data.get("servings"), 2) or 2)
    return {
        "ok": True,
        "recipe": recipe_name,
        "instruction_for_agent": (
            f"Provide a detailed recipe for: '{recipe_name}' ({servings} servings). "
            f"Dietary restrictions: {dietary}. Allergies: {allergies}. "
            "Include: ingredients list, step-by-step instructions, prep/cook time, "
            "and per-serving macros (calories, protein, carbs, fat). "
            "Keep it practical and accessible."
        ),
        "context": {
            "recipe": recipe_name,
            "servings": servings,
            "dietary_preference": dietary,
            "allergies": allergies,
        },
    }


def generate_motivation(data: dict[str, Any]) -> dict[str, Any]:
    profile = _profile_from_input(data)
    goal = _text(profile.get("goal"), "staying healthy")
    progress = get_progress_data({"days": 7})
    streak = progress.get("streak_days", 0)
    workouts_this_week = progress.get("workouts_completed", 0)
    mood = _text(data.get("mood") or data.get("feeling"), "neutral")
    return {
        "ok": True,
        "instruction_for_agent": (
            f"Write a personalised motivational message for someone with goal: '{goal}'. "
            f"Streak: {streak} days. Workouts this week: {workouts_this_week}. "
            f"Current mood: {mood}. "
            "Be genuine, specific to their numbers, and encouraging without being generic."
        ),
        "context": {
            "goal": goal,
            "streak": streak,
            "workouts_this_week": workouts_this_week,
            "mood": mood,
        },
    }


def enforce_dietary_restrictions(data: dict[str, Any]) -> dict[str, Any]:
    meal = _text(data.get("meal") or data.get("food"), "")
    profile = _profile_from_input(data)
    dietary = _text(
        profile.get("dietary_preference") or data.get("dietary_preference"), ""
    ).lower()
    raw_allergies = profile.get("allergies") or data.get("allergies") or ""
    allergies = [a.strip().lower() for a in str(raw_allergies).split(",") if a.strip()]

    restrictions_map = {
        "vegan": ["meat", "chicken", "beef", "pork", "fish", "seafood", "dairy", "milk", "cheese", "egg", "honey"],
        "vegetarian": ["meat", "chicken", "beef", "pork", "fish", "seafood"],
        "gluten-free": ["wheat", "bread", "pasta", "gluten", "flour", "barley", "rye"],
        "dairy-free": ["milk", "cheese", "butter", "cream", "dairy", "yogurt", "whey"],
        "halal": ["pork", "alcohol", "wine", "beer"],
        "kosher": ["pork", "shellfish", "shrimp", "crab", "lobster"],
    }

    violations = []
    meal_lower = meal.lower()
    for pref, blocked in restrictions_map.items():
        if pref in dietary:
            for item in blocked:
                if item in meal_lower:
                    violations.append(f"{item} (violates {pref})")
    for allergen in allergies:
        if allergen and allergen in meal_lower:
            violations.append(f"{allergen} (allergen)")

    return {
        "ok": True,
        "meal": meal,
        "dietary_preference": dietary,
        "allergies": allergies,
        "violations": violations,
        "is_safe": not violations,
        "message": (
            "This meal fits your dietary requirements."
            if not violations
            else f"Warning — contains: {', '.join(violations)}"
        ),
    }
