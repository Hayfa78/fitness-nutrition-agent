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

user_profile = load_profile()

def save_profile():
    with open(PROFILE_FILE, "w") as file:
        json.dump(user_profile, file, indent=4)

def update_profile(field, value):
    if field in user_profile:
        user_profile[field] = value
        save_profile()

def get_profile():
    return user_profile

def profile_summary():
    return (
        f"Age: {user_profile.get('age')}, "
        f"Weight: {user_profile.get('weight')}, "
        f"Height: {user_profile.get('height')}, "
        f"Goal: {user_profile.get('goal')}, "
        f"Fitness Level: {user_profile.get('fitness_level')}, "
        f"Activity Level: {user_profile.get('activity_level')}, "
        f"Dietary Preference: {user_profile.get('dietary_preference')}, "
        f"Meals Per Day: {user_profile.get('meals_per_day')}"
    )
