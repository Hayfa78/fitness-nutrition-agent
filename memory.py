import json
import os

PROFILE_FILE = "profile.json"

default_profile = {
    "age": None,
    "weight": None,
    "height": None,
    "goal": None,
    "fitness_level": None,
    "activity_level": None,
    "dietary_preference": None,
    "meals_per_day": None
}

def load_profile():
    if os.path.exists(PROFILE_FILE):
        with open(PROFILE_FILE, "r") as file:
            saved_profile = json.load(file)
            return {**default_profile, **saved_profile}
    return default_profile.copy()

def get_profile():
    """Always read fresh from disk — never returns stale cached data."""
    return load_profile()

def update_profile(field, value):
    current = load_profile()
    if field in current:
        current[field] = value
        with open(PROFILE_FILE, "w") as file:
            json.dump(current, file, indent=4)

def profile_summary():
    p = load_profile()
    return (
        f"Age: {p.get('age')}, "
        f"Weight: {p.get('weight')}, "
        f"Height: {p.get('height')}, "
        f"Goal: {p.get('goal')}, "
        f"Fitness Level: {p.get('fitness_level')}, "
        f"Activity Level: {p.get('activity_level')}, "
        f"Dietary Preference: {p.get('dietary_preference')}, "
        f"Meals Per Day: {p.get('meals_per_day')}"
    )
