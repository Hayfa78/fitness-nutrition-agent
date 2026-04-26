import re
import html as html_lib
import streamlit as st
from langchain_core.messages import AIMessage, ToolMessage

from memory import update_profile, get_profile, profile_summary
from agent import FitnessChat
from tools import get_dashboard_data

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(page_title="FitAI Coach", page_icon="🌿", layout="wide")

# ── Global CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
/* Base & background */
.stApp { background-color: #f5f2eb; }
.main .block-container {
    background-color: #f5f2eb;
    padding-top: 1rem;
    max-width: 860px;
}

/* Sidebar */
[data-testid="stSidebar"] > div:first-child { background-color: #eae6db; }
[data-testid="stSidebar"] label { color: #2d2d2d !important; font-weight: 500; }
[data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 { color: #2d2d2d; }

/* Sidebar text inputs */
[data-testid="stSidebar"] .stTextInput > div > div > input {
    background-color: #faf8f3 !important;
    border: 1.5px solid #7c9a6e !important;
    border-radius: 8px !important;
    color: #2d2d2d !important;
}
[data-testid="stSidebar"] .stTextInput > div > div > input:focus {
    box-shadow: 0 0 0 2px rgba(124,154,110,0.25) !important;
    outline: none !important;
}

/* Sidebar buttons — sage green, full-width */
[data-testid="stSidebar"] .stButton > button {
    background-color: #7c9a6e !important;
    color: white !important;
    border: none !important;
    border-radius: 10px !important;
    font-weight: 600 !important;
    width: 100%;
    padding: 10px 16px !important;
    transition: background-color 0.2s ease !important;
}
[data-testid="stSidebar"] .stButton > button:hover {
    background-color: #6a8a5c !important;
}

/* Main area buttons — light sage pill (suggested prompts) */
.main .stButton > button {
    background-color: #d4dece !important;
    color: #2d2d2d !important;
    border: none !important;
    border-radius: 20px !important;
    font-size: 0.82rem !important;
    font-weight: 500 !important;
    padding: 7px 14px !important;
    transition: all 0.18s ease !important;
    white-space: nowrap;
}
.main .stButton > button:hover {
    background-color: #c2d4ba !important;
    transform: translateY(-1px);
    box-shadow: 0 3px 10px rgba(0,0,0,0.08) !important;
}

/* Chat bubbles */
.user-bubble {
    background-color: #7c9a6e;
    color: white !important;
    padding: 12px 18px;
    border-radius: 18px 18px 4px 18px;
    margin: 6px 0 6px auto;
    max-width: 68%;
    width: fit-content;
    margin-left: auto;
    box-shadow: 0 2px 8px rgba(124,154,110,0.28);
    font-size: 0.95rem;
    line-height: 1.6;
    display: block;
    word-wrap: break-word;
}
.assistant-bubble {
    background-color: #e8ede4;
    color: #2d2d2d;
    padding: 12px 18px;
    border-radius: 18px 18px 18px 4px;
    margin: 6px 0;
    max-width: 74%;
    width: fit-content;
    box-shadow: 0 2px 8px rgba(0,0,0,0.06);
    font-size: 0.95rem;
    line-height: 1.6;
    display: block;
    word-wrap: break-word;
}

/* Chat input */
[data-testid="stChatInput"] textarea {
    background-color: #faf8f3 !important;
    border: 1.5px solid #7c9a6e !important;
    border-radius: 12px !important;
    color: #2d2d2d !important;
}
[data-testid="stChatInput"] textarea:focus {
    box-shadow: 0 0 0 2px rgba(124,154,110,0.25) !important;
    outline: none !important;
}

/* Dividers */
hr { border-color: #a3b899 !important; border-width: 1px !important; }

/* Profile card */
.profile-card {
    background-color: #f0ece2;
    border: 1.5px solid #a3b899;
    border-radius: 12px;
    padding: 12px 16px;
    margin: 4px 0 8px 0;
    font-size: 0.88rem;
    color: #2d2d2d;
}
.profile-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 5px 0;
    border-bottom: 1px solid #d4dece;
}
.profile-row:last-child { border-bottom: none; }
.profile-row .p-label { font-weight: 600; color: #5a6a54; }
.profile-row .p-value { color: #2d2d2d; }

/* Spinner */
.stSpinner > div { border-top-color: #7c9a6e !important; }

/* Scrollbar */
::-webkit-scrollbar { width: 6px; }
::-webkit-scrollbar-track { background: #f5f2eb; }
::-webkit-scrollbar-thumb { background: #a3b899; border-radius: 3px; }
</style>
""", unsafe_allow_html=True)

# ── Session state ─────────────────────────────────────────────────────────────
if "messages" not in st.session_state:
    st.session_state.messages = [
        {
            "role": "assistant",
            "content": "Hi! I'm FitAI Coach, your personal fitness and nutrition assistant. Ask me about meals, workouts, calories, or your profile."
        }
    ]

if "chat" not in st.session_state:
    st.session_state.chat = FitnessChat()

if "queued_prompt" not in st.session_state:
    st.session_state.queued_prompt = None


# ── Helpers ───────────────────────────────────────────────────────────────────
def _format_ai_content(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = [
            part.get("text", "")
            for part in content
            if isinstance(part, dict) and part.get("type") == "text"
        ]
        return "\n".join(parts).strip()
    return str(content)


def _to_html(text: str) -> str:
    text = html_lib.escape(text)
    text = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', text)
    text = re.sub(r'^- (.+)$', r'• \1', text, flags=re.MULTILINE)
    text = text.replace('\n', '<br>')
    return text


def _get_daily_target() -> int:
    try:
        p = get_profile()
        age = int(str(p.get("age", "")).replace("years", "").strip())
        weight = float(str(p.get("weight", "")).replace("kg", "").strip())
        height = float(str(p.get("height", "")).replace("cm", "").strip())
        goal = str(p.get("goal", "")).lower()
        activity = str(p.get("activity_level", "")).lower()
        mult = {"sedentary": 1.2, "beginner": 1.375, "light": 1.375,
                "moderate": 1.55, "active": 1.725, "very active": 1.9}.get(activity, 1.375)
        bmr = 10 * weight + 6.25 * height - 5 * age + 5
        maintenance = bmr * mult
        if "lose" in goal:
            return round(maintenance - 400)
        if "gain" in goal or "muscle" in goal:
            return round(maintenance + 250)
        return round(maintenance)
    except Exception:
        return 2000


def _get_calories_consumed() -> int:
    total = 0
    for msg in st.session_state.messages:
        if msg["role"] == "assistant":
            for m in re.findall(r"Calories:\s*(\d+)\s*kcal", msg["content"]):
                total += int(m)
    return total


def _profile_val(v) -> str:
    return str(v) if v is not None else "—"




# ── Header ────────────────────────────────────────────────────────────────────
st.markdown("""
<div style="text-align:center; padding:24px 0 8px 0;">
    <h1 style="color:#7c9a6e; font-size:2.4rem; font-weight:700;
               margin-bottom:4px; letter-spacing:-0.5px;">
        🌿 FitAI Coach
    </h1>
    <p style="color:#7c9a6e; font-size:1.05rem; margin:0; opacity:0.82;">
        Your Personal AI Fitness Coach
    </p>
</div>
<hr style="border:none; border-top:1.5px solid #a3b899; margin:12px 0 20px 0;" />
""", unsafe_allow_html=True)

# ── Suggested prompts ─────────────────────────────────────────────────────────
PROMPTS = {
    "🍕 I ate pizza": "I ate pizza",
    "💪 Give me a workout": "Give me a workout plan",
    "🔥 How many calories?": "How many calories should I eat?",
    "👤 Show my profile": "Show my profile",
    "🎯 Lose weight goal": "My goal is lose weight",
}

cols = st.columns(len(PROMPTS))
for col, (label, prompt) in zip(cols, PROMPTS.items()):
    with col:
        if st.button(label, key=f"sp_{label}"):
            st.session_state.queued_prompt = prompt

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown(
        '<h2 style="color:#7c9a6e; font-weight:700; margin-bottom:16px;">🌿 Your Profile</h2>',
        unsafe_allow_html=True
    )

    current_profile = get_profile()

    age = st.text_input("Age", value="" if current_profile.get("age") is None else str(current_profile.get("age")))
    weight = st.text_input("Weight", value="" if current_profile.get("weight") is None else str(current_profile.get("weight")))
    height = st.text_input("Height", value="" if current_profile.get("height") is None else str(current_profile.get("height")))
    goal = st.text_input("Goal", value="" if current_profile.get("goal") is None else str(current_profile.get("goal")))
    fitness_level = st.text_input("Fitness Level", value="" if current_profile.get("fitness_level") is None else str(current_profile.get("fitness_level")))
    activity = st.text_input("Activity Level", value="" if current_profile.get("activity_level") is None else str(current_profile.get("activity_level")))
    dietary_preference = st.text_input("Dietary Preference", value="" if current_profile.get("dietary_preference") is None else str(current_profile.get("dietary_preference")))
    meals_per_day = st.text_input("Meals Per Day", value="" if current_profile.get("meals_per_day") is None else str(current_profile.get("meals_per_day")))

    if st.button("Save Profile", use_container_width=True):
        if age.strip():
            update_profile("age", age.strip())
        if weight.strip():
            update_profile("weight", weight.strip())
        if height.strip():
            update_profile("height", height.strip())
        if goal.strip():
            update_profile("goal", goal.strip())
        if fitness_level.strip():
            update_profile("fitness_level", fitness_level.strip())
        if activity.strip():
            update_profile("activity_level", activity.strip())
        if dietary_preference.strip():
            update_profile("dietary_preference", dietary_preference.strip())
        if meals_per_day.strip():
            update_profile("meals_per_day", meals_per_day.strip())
        st.success("Profile saved.")

    st.divider()

    dashboard = get_dashboard_data()
    st.markdown(
        '<h3 style="color:#7c9a6e; font-weight:700; margin-bottom:10px;">Dashboard</h3>',
        unsafe_allow_html=True
    )
    metric_cols = st.columns(2)
    metric_cols[0].metric("BMI", dashboard["bmi"])
    metric_cols[1].metric("Target", dashboard["calorie_target"])
    metric_cols = st.columns(2)
    metric_cols[0].metric("Workouts", dashboard["workouts_completed"])
    metric_cols[1].metric("Streak", dashboard["streak"])

    # Calorie progress bar
    daily_target = _get_daily_target()
    calories_consumed = _get_calories_consumed()
    ratio = min(calories_consumed / daily_target, 1.0) if daily_target > 0 else 0
    pct = round(ratio * 100)
    bar_color = "#7c9a6e" if ratio < 0.75 else ("#8b9e5e" if ratio < 1.0 else "#c47c6e")
    st.markdown(f"""
<div style="margin:4px 0 12px 0;">
    <div style="font-size:0.82rem; font-weight:600; color:#5a6a54; margin-bottom:6px;">
        Today's Calories
    </div>
    <div style="background:#d4dece; border-radius:6px; height:10px; overflow:hidden;">
        <div style="width:{pct}%; height:100%; background:{bar_color};
                    border-radius:6px; transition:width 0.3s;"></div>
    </div>
    <div style="font-size:0.78rem; color:#7a7a6a; margin-top:5px;">
        {calories_consumed} / {daily_target} kcal
    </div>
</div>
""", unsafe_allow_html=True)

    # Profile card
    p = get_profile()
    st.markdown(f"""
<div class="profile-card">
    <div class="profile-row">
        <span class="p-label">Age</span>
        <span class="p-value">{_profile_val(p.get('age'))}</span>
    </div>
    <div class="profile-row">
        <span class="p-label">Weight</span>
        <span class="p-value">{_profile_val(p.get('weight'))}</span>
    </div>
    <div class="profile-row">
        <span class="p-label">Height</span>
        <span class="p-value">{_profile_val(p.get('height'))}</span>
    </div>
    <div class="profile-row">
        <span class="p-label">Goal</span>
        <span class="p-value">{_profile_val(p.get('goal'))}</span>
    </div>
    <div class="profile-row">
        <span class="p-label">Fitness</span>
        <span class="p-value">{_profile_val(p.get('fitness_level'))}</span>
    </div>
    <div class="profile-row">
        <span class="p-label">Activity</span>
        <span class="p-value">{_profile_val(p.get('activity_level'))}</span>
    </div>
    <div class="profile-row">
        <span class="p-label">Diet</span>
        <span class="p-value">{_profile_val(p.get('dietary_preference'))}</span>
    </div>
    <div class="profile-row">
        <span class="p-label">Meals</span>
        <span class="p-value">{_profile_val(p.get('meals_per_day'))}</span>
    </div>
</div>
""", unsafe_allow_html=True)

    st.divider()
    if st.button("Clear Chat History", use_container_width=True):
        st.session_state.messages = [
            {
                "role": "assistant",
                "content": "Chat history cleared. Ask me anything about fitness and nutrition."
            }
        ]
        st.session_state.chat = FitnessChat()
        st.rerun()

# ── Chat history ──────────────────────────────────────────────────────────────
for message in st.session_state.messages:
    if message["role"] == "user":
        st.markdown(
            f'<div class="user-bubble">{_to_html(message["content"])}</div>',
            unsafe_allow_html=True
        )
    else:
        st.markdown(
            f'<div class="assistant-bubble">'
            f'<span style="margin-right:6px;">🌿</span>{_to_html(message["content"])}'
            f'</div>',
            unsafe_allow_html=True
        )


# ── Chat input ────────────────────────────────────────────────────────────────
user_prompt = st.chat_input("Ask your coach about meals, workouts, calories, or your profile...")

active_prompt = user_prompt
if not active_prompt and st.session_state.queued_prompt:
    active_prompt = st.session_state.queued_prompt
    st.session_state.queued_prompt = None

if active_prompt:
    st.session_state.messages.append({"role": "user", "content": active_prompt})

    st.markdown(
        f'<div class="user-bubble">{_to_html(active_prompt)}</div>',
        unsafe_allow_html=True
    )

    new_messages = []
    with st.spinner("🌿 Thinking..."):
        try:
            new_messages = st.session_state.chat.send_message(active_prompt)
        except Exception as e:
            st.error(str(e))

    ai_parts = [
        _format_ai_content(msg.content)
        for msg in new_messages
        if isinstance(msg, AIMessage) and _format_ai_content(msg.content)
    ]

    if ai_parts:
        combined = "\n".join(ai_parts)
        st.markdown(
            f'<div class="assistant-bubble">'
            f'<span style="margin-right:6px;">🌿</span>{_to_html(combined)}'
            f'</div>',
            unsafe_allow_html=True
        )
        st.session_state.messages.append({"role": "assistant", "content": combined})
    else:
        tool_contents = [
            _format_ai_content(msg.content)
            for msg in new_messages
            if isinstance(msg, ToolMessage)
        ]
        if tool_contents:
            fallback = "\n\n".join(tool_contents)
            st.markdown(
                f'<div class="assistant-bubble">'
                f'<span style="margin-right:6px;">🌿</span>{_to_html(fallback)}'
                f'</div>',
                unsafe_allow_html=True
            )
            st.session_state.messages.append({"role": "assistant", "content": fallback})
