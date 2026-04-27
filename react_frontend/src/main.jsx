import React, { useEffect, useMemo, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  Activity,
  Apple,
  Bot,
  CalendarCheck,
  CheckCircle2,
  Dumbbell,
  Flame,
  Moon,
  Printer,
  Trash2,
  Salad,
  Send,
  Sparkles,
  Target,
  Trophy,
  Utensils,
  Waves
} from "lucide-react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis
} from "recharts";
import "./styles.css";

const API_BASE = import.meta.env.VITE_API_URL || "https://fitness-nutrition-agent.onrender.com";

const KEYS = {
  profile: "fitai_profile",
  meals: "fitai_meals",
  workouts: "fitai_workouts",
  weights: "fitai_weights",
  checkins: "fitai_checkins",
  chat: "fitai_chat",
  checklist: "fitai_workout_checklist",
  mealPlan: "fitai_meal_plan",
  workoutPlan: "fitai_workout_plan",
  theme: "fitai_theme",
  exportedReport: "fitai_exported_report"
};

const emptyProfile = {
  name: "",
  age: "",
  height: "",
  weight: "",
  gender: "male",
  goal: "lose weight",
  activity: "light",
  fitnessLevel: "beginner",
  place: "home",
  restrictions: "",
  budget: "normal",
  workoutTime: "",
  dislikedFoods: "",
  favoriteMeals: "",
  cuisine: "",
  equipment: ""
};

function load(key, fallback) {
  const raw = localStorage.getItem(key);
  return raw ? JSON.parse(raw) : fallback;
}

function save(key, value) {
  localStorage.setItem(key, JSON.stringify(value));
}

function num(value, fallback = 0) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function now() {
  return new Date().toISOString();
}

function todayKey() {
  return now().slice(0, 10);
}

function isRecent(item) {
  const date = new Date();
  date.setDate(date.getDate() - 7);
  return new Date(item.date) >= date;
}

function calculateMetrics(profile) {
  const age = num(profile.age);
  const height = num(profile.height);
  const weight = num(profile.weight);
  if (!age || !height || !weight) return null;
  const genderConstant = profile.gender === "female" ? -161 : profile.gender === "male" ? 5 : -78;
  const multipliers = { sedentary: 1.2, light: 1.375, moderate: 1.55, active: 1.725 };
  const bmr = Math.round(10 * weight + 6.25 * height - 5 * age + genderConstant);
  const tdee = Math.round(bmr * (multipliers[profile.activity] || 1.375));
  const adjust = profile.goal === "lose weight" ? -400 : profile.goal === "gain muscle" ? 300 : 0;
  const calories = Math.max(1200, tdee + adjust);
  const bmi = +(weight / ((height / 100) ** 2)).toFixed(1);
  const protein = Math.round(weight * (profile.goal === "maintain" ? 1.6 : 2));
  const fat = Math.round((calories * 0.27) / 9);
  const carbs = Math.round((calories - protein * 4 - fat * 9) / 4);
  return { bmi, bmr, tdee, calories, protein, carbs, fat };
}

function greetingFor(profile) {
  const hour = new Date().getHours();
  const time = hour < 12 ? "Good morning" : hour < 18 ? "Good afternoon" : "Good evening";
  const name = profile.name?.trim() || "there";
  return `${time}, ${name}. Ready for today's plan?`;
}

function lastWorkoutText(workouts) {
  const last = workouts[workouts.length - 1];
  return last ? last.text : "No workout logged yet";
}

async function readApiJson(response) {
  const text = await response.text();
  if (!text.trim()) {
    throw new Error("Coach is temporarily unavailable. Please try again.");
  }
  try {
    return JSON.parse(text);
  } catch {
    throw new Error("Coach is temporarily unavailable. Please try again.");
  }
}

function buildWorkout(profile) {
  const map = {
    beginner: { days: 3, sets: "2-3", reps: "10-15", rest: "45-60 sec" },
    intermediate: { days: 4, sets: "3-4", reps: "8-12", rest: "60-90 sec" },
    advanced: { days: 5, sets: "4", reps: "6-10", rest: "90 sec" }
  };
  const level = map[profile.fitnessLevel] || map.beginner;
  const home = profile.place === "home";
  const exercises = home
    ? ["Bodyweight squat", "Push-up", "Reverse lunge", "Backpack row", "Glute bridge", "Plank"]
    : ["Leg press", "Bench press", "Lat pulldown", "Romanian deadlift", "Cable row", "Shoulder press"];
  return { ...level, exercises };
}

function App() {
  const [profile, setProfile] = useState(() => load(KEYS.profile, emptyProfile));
  const [meals, setMeals] = useState(() => load(KEYS.meals, []));
  const [workouts, setWorkouts] = useState(() => load(KEYS.workouts, []));
  const [weights, setWeights] = useState(() => load(KEYS.weights, []));
  const [checkins, setCheckins] = useState(() => load(KEYS.checkins, []));
  const [chat, setChat] = useState(() => load(KEYS.chat, [
    { role: "bot", text: "Hi, I am FitAI. Ask me about meals, workouts, or progress.", date: now() }
  ]));
  const [checklist, setChecklist] = useState(() => load(KEYS.checklist, []));
  const [mealPlan, setMealPlan] = useState(() => load(KEYS.mealPlan, null));
  const [workoutPlan, setWorkoutPlan] = useState(() => load(KEYS.workoutPlan, null));
  const [theme, setTheme] = useState(() => load(KEYS.theme, "light"));
  const [toolOutput, setToolOutput] = useState("Choose an AI tool to generate a personalized result.");
  const [message, setMessage] = useState("");
  const [toasts, setToasts] = useState([]);
  const [weeklyReport, setWeeklyReport] = useState("");
  const [activeTab, setActiveTab] = useState("dashboard");

  const metrics = useMemo(() => calculateMetrics(profile), [profile]);
  const profileReady = Boolean(profile.age && profile.height && profile.weight && profile.goal && profile.activity);
  const recentMeals = meals.filter(isRecent);
  const recentWorkouts = workouts.filter(isRecent);
  const todayMeals = meals.filter((meal) => meal.date.slice(0, 10) === todayKey());
  const proteinToday = todayMeals.reduce((sum, meal) => sum + num(meal.protein), 0);
  const caloriesToday = todayMeals.reduce((sum, meal) => sum + num(meal.calories), 0);
  const streak = getStreak(workouts);

  function showToast(text) {
    const toast = { id: Date.now(), text };
    setToasts((items) => [...items, toast]);
    setTimeout(() => {
      setToasts((items) => items.filter((item) => item.id !== toast.id));
    }, 2600);
  }

  function persist(key, setter, value) {
    setter(value);
    save(key, value);
  }

  function buildContext() {
    return {
      profile,
      calculatedMetrics: metrics,
      meals,
      workouts,
      weights,
      checkins,
      context: {
        goal: profile.goal,
        level: profile.fitnessLevel,
        trainingPlace: profile.place,
        allergies: profile.restrictions,
        lastWorkout: lastWorkoutText(workouts),
        mealsLoggedToday: todayMeals.map((meal) => meal.text),
        preferredWorkoutTime: profile.workoutTime,
        dislikedFoods: profile.dislikedFoods,
        favoriteMeals: profile.favoriteMeals,
        preferredCuisine: profile.cuisine,
        equipmentAvailable: profile.equipment
      }
    };
  }

  function formatToolResult(tool, result) {
    if (!result?.data) return result?.reply || "";
    if (tool === "workout") {
      const days = result.data.days || [];
      const exercises = result.data.exercises || [];
      const lines = [
        result.data.summary || "AI workout plan generated.",
        `Days per week: ${result.data.days_per_week || "custom"}`,
        `Difficulty: ${result.data.difficulty || profile.fitnessLevel}`,
        result.data.progression ? `Progression: ${result.data.progression}` : ""
      ];
      if (days.length) {
        days.forEach((day) => {
          lines.push(`\n${day.name || "Day"}:`);
          (day.exercises || []).forEach((ex) => lines.push(
            `- ${ex.name}: ${ex.sets || 3} sets x ${ex.reps || "10-12"}, rest ${ex.rest || "60 sec"}`
          ));
        });
      } else if (exercises.length) {
        lines.push("\nExercises:");
        exercises.forEach((ex) => lines.push(
          `- ${ex.name}: ${ex.sets || 3} sets x ${ex.reps || "10-12"}, rest ${ex.rest || "60 sec"}`
        ));
      }
      return lines.filter(Boolean).join("\n");
    }
    if (tool === "meal_plan") {
      const meals = result.data.meals || [];
      return [
        result.data.summary || "AI meal plan generated.",
        meals.length ? "\nMeals:" : "",
        ...meals.map((meal) => (
          `- ${meal.name}: ${meal.food} (${meal.calories} kcal | P ${meal.protein}g | C ${meal.carbs}g | F ${meal.fat}g)`
        )),
        result.data.notes ? `\nNotes: ${result.data.notes}` : ""
      ].filter(Boolean).join("\n");
    }
    if (tool === "meal_estimate") {
      return `${result.data.meal}: ${result.data.calories} kcal | P ${result.data.protein}g | C ${result.data.carbs}g | F ${result.data.fat}g\n${result.data.note || ""}`;
    }
    return result.reply || JSON.stringify(result.data, null, 2);
  }

  async function runAITool(tool, extraLogs = {}) {
    if (!profileReady) {
      setToolOutput("Complete your profile first so FitAI can personalize this with the API.");
      showToast("Complete profile first");
      return null;
    }
    setToolOutput("FitAI is generating your personalized result...");
    try {
      const response = await fetch("https://fitness-nutrition-agent.onrender.com/tool", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          tool,
          profile,
          logs: { ...buildContext(), ...extraLogs }
        })
      });
      const result = await readApiJson(response);
      if (!response.ok) throw new Error(result.error || "API error");
      setToolOutput(formatToolResult(tool, result));
      return result;
    } catch (error) {
      setToolOutput(error.message || "Coach is temporarily unavailable. Please try again.");
      return null;
    }
  }

  function submitProfile(event) {
    event.preventDefault();
    persist(KEYS.profile, setProfile, profile);
    setToolOutput("Profile saved. FitAI can now personalize your plan.");
    showToast("Profile saved");
  }

  async function addMeal(text) {
    const mealText = text || "Meal";
    setToolOutput("FitAI is estimating this meal with your API...");
    const result = await runAITool("meal_estimate", { meal_to_estimate: mealText });
    if (!result?.data) return;
    const meal = {
      text: result.data.meal || mealText,
      calories: num(result.data.calories),
      protein: num(result.data.protein),
      carbs: num(result.data.carbs),
      fat: num(result.data.fat),
      date: now()
    };
    persist(KEYS.meals, setMeals, [...meals, meal]);
    setToolOutput(`AI meal estimate logged: ${meal.text}\n${meal.calories} kcal | P ${meal.protein}g | C ${meal.carbs}g | F ${meal.fat}g\n${result.data.note || ""}`);
    showToast("AI meal logged");
  }

  function addWorkout(text) {
    persist(KEYS.workouts, setWorkouts, [...workouts, { text: text || "Workout", date: now() }]);
    setToolOutput("Workout logged. Your progress cards are updated.");
    showToast("Workout logged");
  }

  async function generateWorkout() {
    const result = await runAITool("workout");
    if (!result) return;
    // Support new per-day structure; fall back to flat exercises or built-in list
    let aiExercises;
    if (result.data?.days?.length) {
      aiExercises = result.data.days.flatMap((day) => day.exercises || []);
    } else if (result.data?.exercises?.length) {
      aiExercises = result.data.exercises;
    } else {
      aiExercises = buildWorkout(profile).exercises.map((name) => ({ name, sets: 3, reps: "10-12", rest: "60 sec" }));
    }
    const newChecklist = aiExercises.map((exercise, index) => ({
      id: `${Date.now()}-${index}`,
      name: exercise.name,
      target: `${exercise.sets || 3} sets x ${exercise.reps || "10-12"}, rest ${exercise.rest || "60 sec"}`,
      completedSets: 0,
      skipped: false,
      difficulty: "medium",
      date: now()
    }));
    persist(KEYS.checklist, setChecklist, newChecklist);
    persist(KEYS.workoutPlan, setWorkoutPlan, result.data || { summary: result.reply, exercises: aiExercises });
    showToast("AI workout plan saved");
  }

  async function generateMealPlan() {
    const result = await runAITool("meal_plan");
    if (result?.data) {
      persist(KEYS.mealPlan, setMealPlan, result.data);
      showToast("AI meal plan saved");
    } else if (result?.reply) {
      persist(KEYS.mealPlan, setMealPlan, { summary: result.reply, meals: [] });
      showToast("AI meal plan saved");
    }
  }

  async function sendChat(text) {
    const userText = text || message.trim();
    if (!userText) return;
    setMessage("");
    const waiting = [...chat, { role: "user", text: userText, date: now() }, { role: "bot", text: "FitAI is thinking...", typing: true, date: now() }];
    persist(KEYS.chat, setChat, waiting);
    try {
      const response = await fetch("https://fitness-nutrition-agent.onrender.com/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: userText,
          profile,
          logs: buildContext()
        })
      });
      const data = await readApiJson(response);
      if (!response.ok) throw new Error(data.error || "API error");
      waiting[waiting.length - 1].text = data.reply;
      waiting[waiting.length - 1].typing = false;
    } catch (error) {
      waiting[waiting.length - 1].text = error.message || "Coach is temporarily unavailable. Please try again.";
      waiting[waiting.length - 1].typing = false;
    }
    persist(KEYS.chat, setChat, [...waiting]);
  }

  const chartData = [
    { name: "Meals", value: recentMeals.length },
    { name: "Workouts", value: recentWorkouts.length },
    { name: "Check-ins", value: checkins.filter(isRecent).length },
    { name: "Protein", value: Math.round(proteinToday / 10) }
  ];

  const achievements = [
    ["3-day streak", streak >= 3],
    ["Protein goal", metrics && proteinToday >= metrics.protein],
    ["7 meals logged", meals.length >= 7],
    ["First report", load(KEYS.exportedReport, false)]
  ];

  const tabs = [
    ["dashboard", "Dashboard"],
    ["training", "Training"],
    ["nutrition", "Nutrition"],
    ["progress", "Progress"],
    ["coach", "Coach"]
  ];

  return (
    <div className={`app ${theme}`}>
      <div className="toast-stack">{toasts.map((toast) => <div className="toast" key={toast.id}>{toast.text}</div>)}</div>
      <aside className="sidebar">
        <Brand />
        <ProfileForm profile={profile} setProfile={setProfile} onSubmit={submitProfile} />
        <QuickLogs onMeal={addMeal} onWorkout={addWorkout} onWeight={(weight) => persist(KEYS.weights, setWeights, [...weights, { weight: num(weight), date: now() }])} />
      </aside>

      <main>
        <section className="hero">
          <div>
            <span className="pill"><Sparkles size={14} /> AI fitness workspace</span>
            <h1>{greetingFor(profile)}</h1>
            <p>Personal meal ideas, training plans, check-ins, and progress reports based on your profile.</p>
          </div>
          <div className="hero-actions">
            <button className="secondary" onClick={() => {
              const next = theme === "dark" ? "light" : "dark";
              setTheme(next);
              save(KEYS.theme, next);
            }}><Moon size={18} /> {theme === "dark" ? "Light" : "Dark"}</button>
            <button className="secondary compact" onClick={() => {
              save(KEYS.exportedReport, true);
              showToast("Report exported");
              window.print();
            }}><Printer size={18} /> Export</button>
            <button className="danger compact" onClick={() => {
              if (!confirm("Reset all local FitAI data?")) return;
              Object.values(KEYS).forEach((key) => localStorage.removeItem(key));
              showToast("Data reset");
              setTimeout(() => location.reload(), 500);
            }}><Trash2 size={18} /> Reset</button>
          </div>
        </section>

        {!profileReady && <div className="notice">Complete your profile to unlock your personalized plan.</div>}

        <nav className="tabs" aria-label="FitAI sections">
          {tabs.map(([key, label]) => (
            <button
              className={activeTab === key ? "active" : ""}
              key={key}
              onClick={() => setActiveTab(key)}
              type="button"
            >
              {label}
            </button>
          ))}
        </nav>

        <section className="tab-panel" key={activeTab}>
          {activeTab === "dashboard" && <>
            <TodayBoard metrics={metrics} profile={profile} meals={todayMeals} workouts={workouts} proteinToday={proteinToday} />
            <Dashboard metrics={metrics} workouts={recentWorkouts.length} streak={streak} proteinToday={proteinToday} profile={profile} weights={weights} />
            <Tools metrics={metrics} output={toolOutput} actions={{ metrics: () => runAITool("calories"), generateWorkout, generateMealPlan, hydration: () => runAITool("hydration"), groceries: () => runAITool("groceries"), recovery: () => runAITool("recovery") }} />
          </>}

          {activeTab === "training" && <>
            <WorkoutBoard workouts={workouts} checklist={checklist} />
            <section className="content-grid">
              <Checklist checklist={checklist} setChecklist={(items) => persist(KEYS.checklist, setChecklist, items)} addWorkout={addWorkout} />
              <SavedWorkoutPlan plan={workoutPlan} onRegenerate={generateWorkout} onClear={() => {
                persist(KEYS.workoutPlan, setWorkoutPlan, null);
                persist(KEYS.checklist, setChecklist, []);
              }} />
            </section>
          </>}

          {activeTab === "nutrition" && <>
            <NutritionBoard meals={todayMeals} mealPlan={mealPlan} />
            <section className="content-grid">
              <MealPlanCards plan={mealPlan} onRegenerate={generateMealPlan} onClear={() => persist(KEYS.mealPlan, setMealPlan, null)} />
              <MealDiary meals={todayMeals} calories={caloriesToday} protein={proteinToday} />
            </section>
          </>}

          {activeTab === "progress" && <>
            <section className="content-grid">
              <Charts data={chartData} />
              <Achievements achievements={achievements} />
            </section>
            <section className="content-grid">
              <WeeklyReport metrics={metrics} meals={recentMeals.length} workouts={recentWorkouts.length} streak={streak} report={weeklyReport} onGenerate={async () => {
                const result = await runAITool("weekly_report");
                if (result?.reply) setWeeklyReport(result.reply);
              }} />
              <Checkin onSave={(entry) => persist(KEYS.checkins, setCheckins, [...checkins, entry])} />
            </section>
          </>}

          {activeTab === "coach" && <ChatPanel chat={chat} message={message} setMessage={setMessage} sendChat={sendChat} />}
        </section>

        <p className="disclaimer">FitAI gives educational fitness and nutrition estimates. For medical conditions, injuries, eating disorders, or strict diets, ask a qualified professional.</p>

      </main>
    </div>
  );
}

function Brand() {
  return <div className="brand"><div className="brand-mark">AI</div><div><strong>FitAI</strong><span>Private local fitness profile</span></div></div>;
}

function ProfileForm({ profile, setProfile, onSubmit }) {
  const field = (key, value) => setProfile({ ...profile, [key]: value });
  return <form className="panel profile" onSubmit={onSubmit}>
    <h2>Profile</h2>
    <label>Name<input value={profile.name || ""} onChange={(e) => field("name", e.target.value)} placeholder="Layane" /></label>
    <div className="form-grid">
      <label>Age<input value={profile.age} onChange={(e) => field("age", e.target.value)} /></label>
      <label>Gender<select value={profile.gender} onChange={(e) => field("gender", e.target.value)}><option>male</option><option>female</option><option>other</option></select></label>
      <label>Height cm<input value={profile.height} onChange={(e) => field("height", e.target.value)} /></label>
      <label>Weight kg<input value={profile.weight} onChange={(e) => field("weight", e.target.value)} /></label>
      <label>Goal<select value={profile.goal} onChange={(e) => field("goal", e.target.value)}><option>lose weight</option><option>gain muscle</option><option>maintain</option></select></label>
      <label>Activity<select value={profile.activity} onChange={(e) => field("activity", e.target.value)}><option>sedentary</option><option>light</option><option>moderate</option><option>active</option></select></label>
      <label>Level<select value={profile.fitnessLevel} onChange={(e) => field("fitnessLevel", e.target.value)}><option>beginner</option><option>intermediate</option><option>advanced</option></select></label>
      <label>Place<select value={profile.place} onChange={(e) => field("place", e.target.value)}><option>home</option><option>gym</option></select></label>
    </div>
    <label>Allergies or restrictions<input value={profile.restrictions} onChange={(e) => field("restrictions", e.target.value)} /></label>
    <div className="form-grid">
      <label>Workout time<input value={profile.workoutTime || ""} onChange={(e) => field("workoutTime", e.target.value)} placeholder="morning, evening..." /></label>
      <label>Equipment<input value={profile.equipment || ""} onChange={(e) => field("equipment", e.target.value)} placeholder="dumbbells, bands..." /></label>
      <label>Disliked foods<input value={profile.dislikedFoods || ""} onChange={(e) => field("dislikedFoods", e.target.value)} placeholder="tuna, oats..." /></label>
      <label>Favorite meals<input value={profile.favoriteMeals || ""} onChange={(e) => field("favoriteMeals", e.target.value)} placeholder="chicken rice..." /></label>
    </div>
    <label>Preferred cuisine<input value={profile.cuisine || ""} onChange={(e) => field("cuisine", e.target.value)} placeholder="Lebanese, Mediterranean..." /></label>
    <button className="primary">Save Profile</button>
  </form>;
}

function QuickLogs({ onMeal, onWorkout, onWeight }) {
  const [meal, setMeal] = useState("");
  const [workout, setWorkout] = useState("");
  const [weight, setWeight] = useState("");
  return <section className="panel quick">
    <h2>Quick Logs</h2>
    <input placeholder="Meal: chicken and rice" value={meal} onChange={(e) => setMeal(e.target.value)} />
    <button onClick={() => onMeal(meal)}><Utensils size={16} /> Log meal</button>
    <input placeholder="Workout: completed leg day" value={workout} onChange={(e) => setWorkout(e.target.value)} />
    <button onClick={() => onWorkout(workout)}><Dumbbell size={16} /> Log workout</button>
    <input placeholder="Weight kg" value={weight} onChange={(e) => setWeight(e.target.value)} />
    <button onClick={() => onWeight(weight)}><Activity size={16} /> Log weight</button>
  </section>;
}

function Dashboard({ metrics, workouts, streak, proteinToday, profile, weights }) {
  const weightChange = weights.length >= 2 ? `${(weights[weights.length - 1].weight - weights[0].weight).toFixed(1)} kg` : "Log weight";
  const workoutStatus = workouts >= 3 ? "On track" : `${Math.max(3 - workouts, 0)} left`;
  const base = [[Target, "BMI", metrics ? metrics.bmi : "Complete profile"]];
  const goalCards = profile.goal === "gain muscle"
    ? [[Apple, "Protein", metrics ? `${metrics.protein}g` : "Set target"], [Dumbbell, "Strength", workoutStatus], [CalendarCheck, "Workouts", `${workouts}/3`]]
    : profile.goal === "maintain"
      ? [[Flame, "Calories", metrics ? metrics.calories : "Calculate target"], [CalendarCheck, "Consistency", `${workouts}/3 workouts`], [Salad, "Meals", `${proteinToday}g protein today`]]
      : [[Flame, "Calories", metrics ? metrics.calories : "Calculate target"], [Activity, "Cardio", `${workouts}/3 done`], [Target, "Weight Change", weightChange]];
  const cards = [...base, ...goalCards, [CalendarCheck, "Streak", `${streak}d`], [Salad, "Protein Today", `${proteinToday}g`]];
  return <section className="cards">{cards.map(([Icon, label, value]) => <article className="metric-card" key={label}><Icon size={20} /><span>{label}</span><strong>{value}</strong></article>)}</section>;
}

function TodayBoard({ metrics, profile, meals, workouts, proteinToday }) {
  const today = todayKey();
  const workoutDone = workouts.some((item) => item.date.slice(0, 10) === today);
  const water = metrics ? Math.round(num(profile.weight, 70) * 35) : 0;
  const proteinPercent = metrics ? Math.min(Math.round((proteinToday / metrics.protein) * 100), 100) : 0;
  const waterPercent = water ? Math.min(Math.round((0 / water) * 100), 100) : 0;
  const savedCheckins = load(KEYS.checkins, []);
  const lastCheckin = savedCheckins[savedCheckins.length - 1];
  const lowRecovery = lastCheckin && (["low", "okay"].includes(lastCheckin.energy) || ["moderate", "high"].includes(lastCheckin.soreness));
  const recoveryAdvice = lowRecovery ? "Keep it light and prioritize recovery" : "Ready for normal training";

  return <article className="board-card board-today">
    <div className="board-heading"><div><span>Today</span><h2>Daily Plan</h2></div><Sparkles size={22} /></div>
    <div className="board-list">
      <div className="board-row"><span>Workout</span><strong>{workoutDone ? "Completed" : "Strength session"}</strong></div>
      <div className="board-row progress-row"><span>Water</span><strong>{water ? `${(water / 1000).toFixed(1)}L target` : "Complete profile"}</strong><ProgressBar value={waterPercent} tone="green" /></div>
      <div className="board-row progress-row"><span>Protein</span><strong>{metrics ? `${proteinToday}g / ${metrics.protein}g` : "Set target"}</strong><ProgressBar value={proteinPercent} tone="green" /></div>
      <div className="board-row"><span>Meals</span><strong>{meals.length ? `${meals.length} logged` : "Log first meal"}</strong></div>
      <div className="board-row"><span>Recovery</span><strong>{recoveryAdvice}</strong></div>
    </div>
  </article>;
}

function WorkoutBoard({ checklist }) {
  function parseTotalSets(item) {
    const match = String(item.target || "").match(/(\d+)/);
    return match ? parseInt(match[1], 10) : 3;
  }
  const planned     = checklist.filter((item) => !item.skipped && item.completedSets === 0);
  const inProgress  = checklist.filter((item) => !item.skipped && item.completedSets > 0 && item.completedSets < parseTotalSets(item));
  const completedItems = checklist.filter((item) => !item.skipped && item.completedSets >= parseTotalSets(item));

  return <article className="board-card board-workout">
    <div className="board-heading"><div><span>Workout</span><h2>Training Flow</h2></div><Dumbbell size={22} /></div>
    <div className="kanban">
      <KanbanColumn title="Planned" items={planned.map((item) => item.name)} empty="Generate a plan" />
      <KanbanColumn title="In Progress" items={inProgress.map((item) => item.name)} empty="Start a set" />
      <KanbanColumn title="Completed" items={completedItems.map((item) => item.name)} empty="None yet" />
    </div>
  </article>;
}

function NutritionBoard({ mealPlan }) {
  const [openMeal, setOpenMeal] = useState("");
  const mealSlots = ["Breakfast", "Lunch", "Dinner", "Snack"];
  const planMeals = mealPlan?.meals || [];
  const selectedMeal = planMeals.find((meal) => String(meal.name).toLowerCase().includes(openMeal.toLowerCase()));

  return <article className="board-card board-nutrition">
    <div className="board-heading"><div><span>Nutrition</span><h2>Meal Targets</h2></div><Utensils size={22} /></div>
    <div className="nutrition-slots">
      {mealSlots.map((slot) => {
        const plannedMeal = planMeals.find((meal) => String(meal.name).toLowerCase().includes(slot.toLowerCase()));
        const mealName = plannedMeal?.food ? shortMealName(plannedMeal.food) : (slot === "Snack" ? "Plan snack" : `Plan ${slot.toLowerCase()}`);
        const isOpen = openMeal === slot;
        return <button
          className={`nutrition-slot ${isOpen ? "active" : ""}`}
          key={slot}
          onClick={() => setOpenMeal(isOpen ? "" : slot)}
          title={plannedMeal?.food || mealName}
          type="button"
        >
          <span>{slot}</span>
          <strong>{mealName}</strong>
          {plannedMeal && <small>{plannedMeal.calories} kcal | {plannedMeal.protein}g protein</small>}
        </button>;
      })}
    </div>
    {selectedMeal && <div className="meal-detail">
      <span>{openMeal}</span>
      <strong>{selectedMeal.food}</strong>
      <small>{selectedMeal.calories} kcal | Protein {selectedMeal.protein}g | Carbs {selectedMeal.carbs}g | Fat {selectedMeal.fat}g</small>
    </div>}
  </article>;
}

function BoardDeck({ metrics, profile, meals, workouts, checklist, mealPlan, proteinToday }) {
  return <section className="board-deck">
    <TodayBoard metrics={metrics} profile={profile} meals={meals} workouts={workouts} proteinToday={proteinToday} />
    <WorkoutBoard checklist={checklist} />
    <NutritionBoard mealPlan={mealPlan} />
  </section>;
}

function shortMealName(text) {
  const value = String(text || "").split("(")[0].trim();
  return value.length > 34 ? `${value.slice(0, 34).trim()}...` : value;
}

function ProgressBar({ value, tone }) {
  return <div className={`progress-bar ${tone || ""}`}><span style={{ width: `${Math.min(Math.max(value, 0), 100)}%` }} /></div>;
}

function KanbanColumn({ title, items, empty }) {
  return <div className="kanban-column">
    <span>{title}</span>
    <div className="kanban-stack" style={{ maxHeight: "400px", overflowY: "auto" }}>
      {items.length ? items.map((item) => <strong className="kanban-card" key={item}>{item}</strong>) : <em>{empty}</em>}
    </div>
  </div>;
}

function TodayStatus({ metrics, profile, meals, workouts, proteinToday }) {
  const today = todayKey();
  const workoutDone = workouts.some((item) => item.date.slice(0, 10) === today);
  const water = metrics ? Math.round(num(profile.weight, 70) * 35) : 0;
  const proteinPercent = metrics ? Math.min(Math.round((proteinToday / metrics.protein) * 100), 100) : 0;
  const savedCheckins = load(KEYS.checkins, []);
  const lastCheckin = savedCheckins[savedCheckins.length - 1];
  const lowRecovery = lastCheckin && (["low", "okay"].includes(lastCheckin.energy) || ["moderate", "high"].includes(lastCheckin.soreness));
  const highEnergy = lastCheckin && lastCheckin.energy === "high";
  const adaptivePlan = lowRecovery ? "Recovery day" : highEnergy ? "Normal workout" : workouts.length % 2 === 0 ? "Strength session" : "Cardio or mobility";
  const items = [
    ["Workout", workoutDone ? "Completed today" : adaptivePlan],
    ["Water", water ? `${(water / 1000).toFixed(1)}L target` : "Complete profile"],
    ["Protein", metrics ? `${proteinToday}g / ${metrics.protein}g (${proteinPercent}%)` : "Set target"],
    ["Meals", meals.length ? `${meals.length} logged today` : "Log your first meal"]
  ];
  return <section className="today-bar">
    <div className="today-head"><Sparkles size={20} /><strong>Today</strong></div>
    {items.map(([label, value]) => <div className="today-item" key={label}><span>{label}</span><strong>{value}</strong></div>)}
  </section>;
}

function ChatPanel({ chat, message, setMessage, sendChat }) {
  const endRef = useRef(null);
  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chat]);
  return <section className="panel chat-panel">
    <div className="section-heading"><h2><Bot size={20} /> FitAI Chat</h2><span>Personalized chat</span></div>
    <div className="chat-window">
      {chat.map((msg, index) => <div className={`bubble ${msg.role} ${msg.typing ? "typing" : ""}`} key={index}>{msg.text}</div>)}
      <div ref={endRef} />
    </div>
    <form className="chat-input" onSubmit={(e) => { e.preventDefault(); sendChat(); }}>
      <input value={message} onChange={(e) => setMessage(e.target.value)} placeholder="Ask FitAI about meals, workouts, recovery, or progress..." />
      <button className="primary"><Send size={18} /></button>
    </form>
  </section>;
}

function Tools({ actions, output }) {
  const tools = [
    [Flame, "Calories", "BMI, BMR, macros", actions.metrics],
    [Dumbbell, "Workout", "Generate checklist", actions.generateWorkout],
    [Utensils, "Meal Plan", "Meals and macros", actions.generateMealPlan],
    [Waves, "Hydration", "Water target", actions.hydration],
    [Apple, "Groceries", "Shopping list", actions.groceries],
    [Moon, "Recovery", "Sleep and soreness", actions.recovery]
  ];
  return <section className="panel tools-panel">
    <div className="section-heading"><h2>FitAI Tools</h2><span>API generated</span></div>
    <div className="tool-grid">{tools.map(([Icon, title, desc, action]) => <button key={title} onClick={action}><Icon size={20} /><strong>{title}</strong><span>{desc}</span></button>)}</div>
    <div className="tool-output">{output}</div>
  </section>;
}

function Checklist({ checklist, setChecklist, addWorkout }) {
  function update(index, patch) {
    const next = checklist.map((item, i) => i === index ? { ...item, ...patch } : item);
    setChecklist(next);
    if (next.filter((item) => item.completedSets > 0 && !item.skipped).length >= Math.ceil(next.length / 2)) {
      addWorkout("Checklist workout completed");
    }
  }
  return <section className="panel">
    <div className="section-heading"><h2>Workout Checklist</h2><span>Sets, skips, rating</span></div>
    <div className="list">{checklist.length ? checklist.map((item, index) => <div className="list-row" key={item.id}>
      <strong>{item.name}<small>{item.target}</small></strong>
      <input type="number" min="0" max="6" value={item.completedSets} onChange={(e) => update(index, { completedSets: num(e.target.value) })} />
      <select value={item.difficulty} onChange={(e) => update(index, { difficulty: e.target.value })}><option>easy</option><option>medium</option><option>hard</option></select>
      <label className="inline"><input type="checkbox" checked={item.skipped} onChange={(e) => update(index, { skipped: e.target.checked })} /> skipped</label>
    </div>) : <p className="empty-state">Generate a workout plan first</p>}</div>
  </section>;
}

function MealDiary({ meals, calories, protein }) {
  return <section className="panel">
    <div className="section-heading"><h2>Meal Diary</h2><span>{calories} kcal | {protein}g protein</span></div>
    <div className="list">{meals.length ? meals.map((meal) => <div className="list-row diary" key={meal.date}><strong>{meal.text}</strong><span>{meal.calories} kcal</span><span>P {meal.protein} C {meal.carbs} F {meal.fat}</span></div>) : <p className="empty-state">Log your first meal</p>}</div>
  </section>;
}

function MealPlanCards({ plan, onRegenerate, onClear }) {
  const meals = plan?.meals || [];
  return <section className="panel">
    <div className="section-heading"><h2>Saved AI Meal Plan</h2><span>{meals.length ? `${meals.length} meals` : "API generated"}</span></div>
    {!plan && <p className="empty-state">Generate an AI meal plan to save meal cards here.</p>}
    {plan?.summary && <p className="plan-summary">{plan.summary}</p>}
    <div className="meal-card-grid">
      {meals.map((meal) => <article className="meal-card" key={meal.name}>
        <strong>{meal.name}</strong>
        <span>{meal.food}</span>
        <small>{meal.calories} kcal | P {meal.protein}g | C {meal.carbs}g | F {meal.fat}g</small>
      </article>)}
    </div>
    {plan?.notes && <p className="plan-summary">{plan.notes}</p>}
    <div className="plan-actions">
      <button className="primary" onClick={onRegenerate}>Regenerate</button>
      <button className="secondary" onClick={onClear}>Clear Plan</button>
    </div>
  </section>;
}

function SavedWorkoutPlan({ plan, onRegenerate, onClear }) {
  return <section className="panel">
    <div className="section-heading"><h2>Saved AI Workout Plan</h2><span>{plan?.days_per_week ? `${plan.days_per_week} days/week` : "API generated"}</span></div>
    {!plan && <p className="empty-state">Generate an AI workout plan to save training days here.</p>}
    {plan?.summary && <p className="plan-summary">{plan.summary}</p>}
    {plan?.days?.length > 0 && (
      <div className="workout-tabs">
        {plan.days.map((day, dayIndex) => (
          <article className="workout-tab" key={dayIndex}>
            <strong>{day.name || `Day ${dayIndex + 1}`}</strong>
            <div style={{ maxHeight: "400px", overflowY: "auto", marginTop: "6px" }}>
              {(day.exercises || []).map((ex, i) => (
                <div key={i} style={{ marginBottom: "4px" }}>
                  <span>{ex.name}</span>
                  <small style={{ display: "block" }}>{ex.sets || 3} sets × {ex.reps || "10-12"} | rest {ex.rest || "60 sec"}</small>
                </div>
              ))}
            </div>
          </article>
        ))}
      </div>
    )}
    {!plan?.days?.length && plan?.exercises?.length > 0 && (
      <div className="workout-tabs" style={{ maxHeight: "400px", overflowY: "auto" }}>
        {plan.exercises.map((exercise, index) => (
          <article className="workout-tab" key={`${exercise.name}-${index}`}>
            <strong>Day {index + 1}</strong>
            <span>{exercise.name}</span>
            <small>{exercise.sets || 3} sets x {exercise.reps || "10-12"} | rest {exercise.rest || "60 sec"}</small>
          </article>
        ))}
      </div>
    )}
    {plan?.progression && <p className="plan-summary">Progression: {plan.progression}</p>}
    <div className="plan-actions">
      <button className="primary" onClick={onRegenerate}>Regenerate</button>
      <button className="secondary" onClick={onClear}>Clear Plan</button>
    </div>
  </section>;
}

function Charts({ data }) {
  const hasData = data.some((item) => item.value > 0);
  return <section className="panel">
    <div className="section-heading"><h2>Progress Charts</h2><span>Weekly overview</span></div>
    {hasData ? <ResponsiveContainer width="100%" height={240}>
      <BarChart data={data}><CartesianGrid strokeDasharray="3 3" /><XAxis dataKey="name" /><YAxis allowDecimals={false} /><Tooltip /><Bar dataKey="value" fill="#6f9163" radius={[8, 8, 0, 0]} /></BarChart>
    </ResponsiveContainer> : <p className="empty-state">Log meals/workouts to see trends</p>}
  </section>;
}

function Achievements({ achievements }) {
  return <section className="panel">
    <div className="section-heading"><h2><Trophy size={20} /> Achievements</h2><span>Auto tracked</span></div>
    <div className="achievement-grid">{achievements.map(([label, done]) => <div className={`achievement ${done ? "done" : ""}`} key={label}><CheckCircle2 size={18} /> {label}</div>)}</div>
  </section>;
}

function Checkin({ onSave }) {
  const [entry, setEntry] = useState({ sleep: "", mood: "", soreness: "", energy: "" });
  const options = {
    sleep: ["5 or less", "6 hours", "7 hours", "8+ hours"],
    mood: ["low", "okay", "good", "great"],
    soreness: ["none", "light", "moderate", "high"],
    energy: ["low", "okay", "good", "high"]
  };
  return <section className="panel">
    <div className="section-heading"><h2>Daily Check-In</h2><span>Recovery signals</span></div>
    <div className="form-grid">{Object.keys(entry).map((key) => <label key={key}>{key}<select value={entry[key]} onChange={(e) => setEntry({ ...entry, [key]: e.target.value })}><option value="">Choose</option>{options[key].map((option) => <option key={option}>{option}</option>)}</select></label>)}</div>
    <button className="primary" onClick={() => onSave({ ...entry, date: now() })}>Save Check-In</button>
  </section>;
}

function WeeklyReport({ metrics, meals, workouts, streak, report, onGenerate }) {
  return <section className="panel report-card">
    <div className="section-heading"><h2>Weekly Report</h2><span>Printable</span></div>
    {!report && <div className="empty-state report-empty">
      No weekly report yet. Log meals and workouts, then generate your AI weekly report.
    </div>}
    <button className="primary" onClick={onGenerate}>Generate AI Weekly Report</button>
    {report && <pre className="report-output">{report}</pre>}
  </section>;
}

function getStreak(workouts) {
  const dates = new Set(workouts.map((item) => item.date.slice(0, 10)));
  let streak = 0;
  const date = new Date();
  while (dates.has(date.toISOString().slice(0, 10))) {
    streak += 1;
    date.setDate(date.getDate() - 1);
  }
  return streak;
}

createRoot(document.getElementById("root")).render(<App />);
