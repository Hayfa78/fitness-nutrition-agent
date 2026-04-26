# FitAI Coach - localStorage Version

This folder contains a simple browser-based Fitness and Nutrition AI Coach.

## Project Structure

```text
localstorage_app/
  index.html   # UI layout: dashboard, profile, logs, chat, tools
  style.css    # Clean dashboard styling
  app.js       # localStorage, calculators, tools, frontend chat API call
  api_server.py # local backend that keeps the API key hidden
```

## Storage

No database is used. The app stores data in browser localStorage:

- `fitai_profile`
- `fitai_meals`
- `fitai_workouts`
- `fitai_weights`
- `fitai_checkins`
- `fitai_chat`
- `fitai_meal_plan`
- `fitai_workout_checklist`
- `fitai_theme`
- `fitai_exported_report`

## How To Open With The API

From the main project folder, run:

```powershell
.\.venv\Scripts\python.exe localstorage_app\api_server.py
```

Then open:

```text
http://localhost:8503
```

## API Key Note

The frontend does not include or expose an API key. The chat sends requests to `api_server.py` using `/chat`.
The backend reads `GEMINI_API_KEY` from the project `.env` file.

## Added UI Features

- Workout completion checklist
- Meal diary
- Simple progress charts
- Daily recommendation card
- First-time onboarding steps
- Dark mode saved in localStorage
- Achievements
- Printable weekly report
