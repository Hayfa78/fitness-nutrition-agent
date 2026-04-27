================================================================================
                        FitAI COACH — README
          AI-Powered Personalized Fitness & Nutrition Assistant
================================================================================

PROJECT OVERVIEW
----------------
FitAI Coach is a full-stack AI application that combines a React web frontend
with a Python AI backend. It uses Google Gemini as the LLM, LangGraph for the
agent framework, FAISS for RAG (Retrieval-Augmented Generation), and FastAPI
for the backend API. Users interact through a chat interface and tool buttons
to get personalized fitness and nutrition guidance.

Live Demo:
  Frontend : https://fitai-coach.vercel.app
  Backend  : https://fitness-nutrition-agent.onrender.com/health

================================================================================
PROJECT STRUCTURE
================================================================================

fitness_nutrition_agent/
  app.py                        # Backend entry point — starts the FastAPI server
  agent.py                      # LangGraph ReAct agent + 22 custom tool definitions
  tools.py                      # All tool logic (Type 1: math/logging, Type 2: context collectors)
  rag.py                        # RAG system using FAISS vector search
  memory.py                     # User profile storage (reads/writes profile.json)
  knowledge.txt                 # Fitness/nutrition knowledge base for RAG
  requirements.txt              # Python dependencies
  profile.json                  # Saved user profile (auto-created on first run)
  meal_log.json                 # Meal log (auto-created when meals are logged)
  workout_log.json              # Workout log (auto-created when workouts are logged)
  .env.example                  # Example environment variables file
  .env                          # Your actual API keys (NOT committed to GitHub)

  localstorage_app/
    api_server.py               # FastAPI app — /chat and /tool endpoints

  react_frontend/
    src/
      main.jsx                  # Full React app UI
      styles.css                # Styling — sage green theme + dark mode
    package.json                # Frontend dependencies
    vite.config.js              # Vite build configuration

================================================================================
REQUIREMENTS
================================================================================

PYTHON VERSION: 3.11 or higher

BACKEND DEPENDENCIES (requirements.txt):
  fastapi
  uvicorn
  python-dotenv
  langchain
  langchain-core
  langchain-community
  langchain-google-genai
  langgraph
  faiss-cpu
  google-generativeai
  pydantic

FRONTEND DEPENDENCIES:
  Node.js 18 or higher
  npm 9 or higher
  (all packages listed in react_frontend/package.json)

================================================================================
SETUP INSTRUCTIONS
================================================================================

STEP 1 — GET YOUR GEMINI API KEY
---------------------------------
1. Go to https://aistudio.google.com
2. Sign in with your Google account
3. Click "Get API Key" then "Create API key"
4. Copy the key (starts with "AIza...")

STEP 2 — CREATE YOUR .env FILE
--------------------------------
In the main project folder, create a file called ".env" and add:

  GEMINI_API_KEY=your_api_key_here
  GOOGLE_API_KEY=your_api_key_here
  GEMINI_MODEL=gemini-2.5-flash-lite
  FITAI_PORT=8504

Both GEMINI_API_KEY and GOOGLE_API_KEY should have the same value.
Use the .env.example file as a reference.

STEP 3 — INSTALL PYTHON DEPENDENCIES
--------------------------------------
Open a terminal in the main project folder and run:

  pip install -r requirements.txt

If you are on Windows and get an error, try:

  python -m pip install -r requirements.txt

STEP 4 — INSTALL FRONTEND DEPENDENCIES
----------------------------------------
Open a second terminal and run:

  cd react_frontend
  npm install

================================================================================
HOW TO RUN THE APP (LOCAL)
================================================================================

You need TWO terminals running at the same time.

TERMINAL 1 — Start the Python backend:
  (from the main project folder)

  python app.py

  You should see:
    FitAI API starting on port 8504
    INFO: Uvicorn running on http://0.0.0.0:8504

TERMINAL 2 — Start the React frontend:
  (from the react_frontend folder)

  cd react_frontend
  npm run dev

  You should see:
    VITE ready
    Local: http://127.0.0.1:5173

OPEN IN BROWSER:
  http://127.0.0.1:5173

================================================================================
HOW TO USE THE APP
================================================================================

1. FILL IN YOUR PROFILE
   In the sidebar on the left, enter your age, weight, height, goal,
   activity level, dietary preferences, and allergies. Click "Save Profile".

2. USE THE TOOL BUTTONS
   Click buttons like "Calculate Calories", "Generate Workout", "Meal Plan",
   "Grocery List", "Recovery", or "Weekly Report" for instant AI-generated results.

3. CHAT WITH THE AI COACH
   Go to the Coach tab and type naturally. Examples:
     - "I ate 2 slices of pizza for lunch"
     - "Give me a workout for today"
     - "Am I on track with my calories?"
     - "What is progressive overload?"
     - "My energy is low today, what should I do?"

4. TRACK YOUR PROGRESS
   The app logs meals, workouts, and hydration automatically.
   Check the Progress tab to see your weekly stats.

================================================================================
HOW IT WORKS (TECHNICAL SUMMARY)
================================================================================

AGENT:
  - FitnessChat class in agent.py uses LangGraph's create_react_agent
  - The agent has access to 22 custom tools
  - It decides autonomously which tool to call based on the user's message
  - Conversation history is maintained as HumanMessage/AIMessage objects
  - History is capped at 40 messages to manage token limits

RAG SYSTEM:
  - knowledge.txt is split into sections using # SECTION: headers
  - Each section is converted to a vector embedding using Google's embedding model
  - FAISS stores and searches these embeddings
  - Cosine similarity threshold of 0.75 — only strong matches are used
  - Falls back to LLM knowledge if no relevant section is found

TOOLS (22 total):
  Type 1 (pure math/logging — no LLM):
    calculate_calories, calculate_hydration_needs, record_meal,
    record_workout, record_hydration, record_checkin, get_progress_data,
    check_goal_feasibility, suggest_progressive_overload,
    enforce_dietary_restrictions

  Type 2 (context collectors — feed Gemini):
    generate_meal_plan, generate_workout_plan, estimate_meal,
    generate_grocery_list, generate_recovery_advice, generate_weekly_report,
    generate_recipe, generate_motivation

API ENDPOINTS:
  POST /chat   — Chat with the AI coach
  POST /tool   — Trigger a specific tool (workout, meal plan, etc.)
  GET  /health — Check if the backend is running

================================================================================
DEPLOYMENT
================================================================================

BACKEND (Render):
  - Platform  : https://render.com
  - Runtime   : Python 3
  - Start cmd : python app.py
  - Live URL  : https://fitness-nutrition-agent.onrender.com
  - Set GEMINI_API_KEY and GOOGLE_API_KEY in Render environment variables

FRONTEND (Vercel):
  - Platform  : https://vercel.com
  - Framework : React + Vite
  - Root dir  : react_frontend
  - Live URL  : https://fitai-coach.vercel.app
  - Auto-deploys on every git push to main branch

================================================================================
ENVIRONMENT VARIABLES
================================================================================

Variable          Required    Description
-----------       --------    -----------
GEMINI_API_KEY    Yes         Your Google Gemini API key
GOOGLE_API_KEY    Yes         Same as GEMINI_API_KEY (used by some libraries)
GEMINI_MODEL      No          Model name (default: gemini-2.5-flash-lite)
FITAI_PORT        No          Port number (default: 8504)

================================================================================
TROUBLESHOOTING
================================================================================

Problem: "No module named 'dotenv'"
Solution: pip install python-dotenv

Problem: "No module named 'langchain_community'"
Solution: pip install langchain-community

Problem: "No module named 'uvicorn'"
Solution: pip install uvicorn fastapi

Problem: API key error (INVALID_ARGUMENT or 401)
Solution: Check your .env file — make sure both GEMINI_API_KEY and
          GOOGLE_API_KEY are set to the same valid key with no spaces.

Problem: Quota exceeded (429 error)
Solution: You have hit the daily request limit. Wait until tomorrow
          or switch to a paid Google Cloud API key.

Problem: "streamlit is not recognized"
Solution: Use "python -m streamlit run app.py" instead of "streamlit run app.py"
          Note: The main app now uses React + FastAPI, not Streamlit.

Problem: Frontend shows "Coach is temporarily unavailable"
Solution: Make sure the backend (python app.py) is running in Terminal 1
          before opening the frontend.

Problem: Port already in use
Solution: Change FITAI_PORT in your .env file to another number (e.g. 8505)

================================================================================
TECHNOLOGY STACK
================================================================================

Backend:
  Python 3.11        Programming language
  FastAPI            REST API framework
  Uvicorn            ASGI server
  LangChain          @tool decorator, message types, Gemini wrapper
  LangGraph          create_react_agent — ReAct agent framework
  Google Gemini      Large language model (gemini-2.5-flash-lite)
  FAISS              Vector similarity search for RAG
  Google Embeddings  Text-to-vector conversion (embedding-001)
  python-dotenv      Environment variable management

Frontend:
  React              UI framework
  Vite               Build tool and dev server
  JavaScript (ES6+)  Frontend logic
  CSS3               Styling with sage green theme and dark mode

Deployment:
  Render             Cloud hosting for Python backend
  Vercel             Cloud hosting for React frontend
  GitHub             Version control and auto-deploy trigger

================================================================================
TEAM
================================================================================

Project: FitAI Coach
Course : Large Language Models
Built with Python, LangChain, LangGraph, Google Gemini, React, FastAPI

================================================================================