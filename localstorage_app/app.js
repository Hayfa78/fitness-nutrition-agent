const STORAGE_KEYS = {
  profile: "fitai_profile",
  meals: "fitai_meals",
  workouts: "fitai_workouts",
  weights: "fitai_weights",
  checkins: "fitai_checkins",
  chat: "fitai_chat",
  mealPlan: "fitai_meal_plan",
  workoutChecklist: "fitai_workout_checklist",
  theme: "fitai_theme",
  exportedReport: "fitai_exported_report"
};

const $ = (id) => document.getElementById(id);

function load(key, fallback) {
  const raw = localStorage.getItem(key);
  return raw ? JSON.parse(raw) : fallback;
}

function save(key, value) {
  localStorage.setItem(key, JSON.stringify(value));
}

function today() {
  return new Date().toISOString();
}

function weekAgo() {
  const date = new Date();
  date.setDate(date.getDate() - 7);
  return date;
}

function inLastWeek(item) {
  return new Date(item.date) >= weekAgo();
}

function number(value, fallback = 0) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function getProfile() {
  return load(STORAGE_KEYS.profile, {
    age: "",
    height: "",
    weight: "",
    gender: "male",
    goal: "lose weight",
    activity: "light",
    fitnessLevel: "beginner",
    place: "home",
    restrictions: "",
    budget: "normal"
  });
}

function setProfile(profile) {
  save(STORAGE_KEYS.profile, profile);
}

function isProfileComplete(profile = getProfile()) {
  return Boolean(profile.age && profile.height && profile.weight && profile.goal && profile.activity && profile.fitnessLevel && profile.place);
}

function renderProfileBanner(message = "") {
  const banner = $("profileBanner");
  if (!banner) return;
  if (message) {
    banner.textContent = message;
    banner.className = "banner success";
    return;
  }
  if (!isProfileComplete()) {
    banner.textContent = "Complete your profile to unlock personalized tools.";
    banner.className = "banner warning";
  } else {
    banner.textContent = "Profile saved. Personalized tools are ready.";
    banner.className = "banner success";
  }
}

function requireProfile() {
  if (isProfileComplete()) {
    return true;
  }
  showTool("Complete your profile first so FitAI can personalize this tool for your body, goal, and activity level.");
  return false;
}

function getLogs() {
  return {
    meals: load(STORAGE_KEYS.meals, []),
    workouts: load(STORAGE_KEYS.workouts, []),
    weights: load(STORAGE_KEYS.weights, []),
    checkins: load(STORAGE_KEYS.checkins, [])
  };
}

async function askFitAI(message) {
  const response = await fetch("/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      message,
      profile: getProfile(),
      logs: getLogs()
    })
  });
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.error || "FitAI API request failed.");
  }
  return data.reply;
}

function todayKey() {
  return new Date().toISOString().slice(0, 10);
}

function calculateMetrics(profile = getProfile()) {
  const age = number(profile.age);
  const height = number(profile.height);
  const weight = number(profile.weight);
  if (!age || !height || !weight) {
    return null;
  }

  const genderConstant = profile.gender === "female" ? -161 : profile.gender === "male" ? 5 : -78;
  const bmr = Math.round(10 * weight + 6.25 * height - 5 * age + genderConstant);
  const multipliers = { sedentary: 1.2, light: 1.375, moderate: 1.55, active: 1.725 };
  const tdee = Math.round(bmr * (multipliers[profile.activity] || 1.375));
  const goalAdjust = profile.goal === "lose weight" ? -400 : profile.goal === "gain muscle" ? 300 : 0;
  const calorieTarget = Math.max(1200, tdee + goalAdjust);
  const bmi = +(weight / ((height / 100) ** 2)).toFixed(1);
  const protein = Math.round(weight * (profile.goal === "maintain" ? 1.6 : 2));
  const fat = Math.round((calorieTarget * 0.27) / 9);
  const carbs = Math.round((calorieTarget - protein * 4 - fat * 9) / 4);
  const weeklyChange = profile.goal === "lose weight"
    ? "0.25 to 0.75 kg loss per week"
    : profile.goal === "gain muscle"
      ? "0.1 to 0.25 kg gain per week"
      : "stay within 0.25 kg per week";

  return { bmi, bmr, tdee, calorieTarget, protein, carbs, fat, weeklyChange };
}

function estimateFood(text) {
  const lower = text.toLowerCase();
  const foods = [
    { key: "pizza", calories: 700, protein: 28, carbs: 80, fat: 28 },
    { key: "burger", calories: 650, protein: 32, carbs: 48, fat: 35 },
    { key: "chicken", calories: 320, protein: 42, carbs: 0, fat: 9 },
    { key: "rice", calories: 260, protein: 5, carbs: 56, fat: 1 },
    { key: "salad", calories: 180, protein: 8, carbs: 18, fat: 8 },
    { key: "egg", calories: 150, protein: 12, carbs: 1, fat: 10 },
    { key: "oats", calories: 300, protein: 12, carbs: 48, fat: 7 },
    { key: "pasta", calories: 520, protein: 18, carbs: 82, fat: 14 }
  ];
  const matches = foods.filter((food) => lower.includes(food.key));
  const base = matches.length ? matches : [{ calories: 450, protein: 22, carbs: 48, fat: 16 }];
  return base.reduce((total, item) => ({
    calories: total.calories + item.calories,
    protein: total.protein + item.protein,
    carbs: total.carbs + item.carbs,
    fat: total.fat + item.fat
  }), { calories: 0, protein: 0, carbs: 0, fat: 0 });
}

function safetyCheck(message, metrics = calculateMetrics()) {
  const lower = message.toLowerCase();
  const warnings = [];
  if (/lose\s+\d+.*(day|week)|crash|starv|no food|water fast/.test(lower)) {
    warnings.push("Avoid extreme weight-loss goals. A safer target is slow weekly progress with a moderate deficit.");
  }
  if (metrics && metrics.calorieTarget < metrics.tdee - 700) {
    warnings.push("Your calorie deficit may be too aggressive. Keep the deficit moderate for better recovery.");
  }
  if (/pain|injury|sharp/.test(lower)) {
    warnings.push("Do not train through sharp pain. Switch to recovery work and consider medical advice if pain continues.");
  }
  if (/every day|twice a day|no rest/.test(lower)) {
    warnings.push("Your plan may lack recovery. Include at least 1-2 easier days each week.");
  }
  if (/slept\s+[0-5]|5 hours|4 hours|3 hours/.test(lower)) {
    warnings.push("Low sleep reduces recovery. Keep today's workout lighter and prioritize sleep tonight.");
  }
  return warnings;
}

function generateWorkoutPlan() {
  const profile = getProfile();
  const levelMap = {
    beginner: { days: 3, sets: "2-3", reps: "10-15", rest: "45-60 sec" },
    intermediate: { days: 4, sets: "3-4", reps: "8-12", rest: "60-90 sec" },
    advanced: { days: 5, sets: "4", reps: "6-10", rest: "90 sec" }
  };
  const level = levelMap[profile.fitnessLevel] || levelMap.beginner;
  const home = profile.place === "home";
  const exercises = home
    ? ["Bodyweight squat", "Push-up", "Reverse lunge", "Backpack row", "Glute bridge", "Plank"]
    : ["Leg press", "Bench press", "Lat pulldown", "Romanian deadlift", "Cable row", "Dumbbell shoulder press"];
  saveWorkoutChecklist(exercises.slice(0, 6));

  return `Workout Plan
Goal: ${profile.goal}
Days per week: ${level.days}
Difficulty: ${profile.fitnessLevel}
Version: ${profile.place}

Day 1 - Full Body
- ${exercises[0]}: ${level.sets} sets x ${level.reps}, rest ${level.rest}
- ${exercises[1]}: ${level.sets} sets x ${level.reps}, rest ${level.rest}
- ${exercises[2]}: ${level.sets} sets x ${level.reps}, rest ${level.rest}
- Plank: 3 sets x 30-45 sec

Day 2 - Cardio and Core
- Brisk walk, bike, or incline treadmill: 25-35 min
- Dead bug: 3 sets x 12 reps
- Side plank: 2 sets x 30 sec each side

Day 3 - Strength
- ${exercises[3]}: ${level.sets} sets x ${level.reps}, rest ${level.rest}
- ${exercises[4]}: ${level.sets} sets x ${level.reps}, rest ${level.rest}
- ${exercises[5]}: ${level.sets} sets x ${level.reps}, rest ${level.rest}

Progression:
- Week 1: learn form and finish every session
- Week 2: add 1-2 reps per exercise
- Week 3: add a small amount of weight or one extra set
- Week 4: keep intensity but reduce volume if tired`;
}

function saveWorkoutChecklist(exercises) {
  const checklist = exercises.map((name, index) => ({
    id: `${Date.now()}-${index}`,
    name,
    completedSets: 0,
    skipped: false,
    difficulty: "medium",
    date: today()
  }));
  save(STORAGE_KEYS.workoutChecklist, checklist);
}

function generateMealPlan() {
  const profile = getProfile();
  const metrics = calculateMetrics() || { calorieTarget: 2000, protein: 140, carbs: 220, fat: 60 };
  const mealsPerDay = 3;
  const perMeal = Math.round(metrics.calorieTarget / mealsPerDay);
  const restrictions = profile.restrictions || "none";
  const budgetNote = profile.budget === "low" ? "Use budget foods like eggs, tuna, beans, rice, oats, frozen vegetables." : "Use simple whole foods and repeat meals to stay consistent.";
  const plan = [
    { name: "Breakfast", food: "Oats with Greek yogurt, banana, and cinnamon" },
    { name: "Lunch", food: "Chicken or tofu rice bowl with vegetables" },
    { name: "Dinner", food: "Salmon, eggs, or beans with potatoes and salad" }
  ];
  save(STORAGE_KEYS.mealPlan, plan);
  return `Daily Meal Plan
Calorie target: ${metrics.calorieTarget} kcal
Goal: ${profile.goal}
Meals per day: ${mealsPerDay}
Allergies/restrictions: ${restrictions}
Budget: ${profile.budget}

${plan.map((meal) => `${meal.name}: ${meal.food}
- Estimated: ${perMeal} kcal | Protein ${Math.round(metrics.protein / mealsPerDay)}g | Carbs ${Math.round(metrics.carbs / mealsPerDay)}g | Fat ${Math.round(metrics.fat / mealsPerDay)}g`).join("\n\n")}

Budget note: ${budgetNote}`;
}

function hydrationCalculator() {
  const profile = getProfile();
  const weight = number(profile.weight, 70);
  const bonus = profile.activity === "active" ? 750 : profile.activity === "moderate" ? 500 : profile.activity === "light" ? 250 : 0;
  const total = Math.round(weight * 35 + bonus);
  return `Hydration Target
- Daily water: ${total} ml (${(total / 1000).toFixed(2)} L)
- Add 300-700 ml if you sweat heavily
- Simple habit: drink one cup when you wake up and one cup with each meal`;
}

function groceryList() {
  const plan = load(STORAGE_KEYS.mealPlan, []);
  const base = ["oats", "Greek yogurt", "bananas", "rice", "chicken or tofu", "mixed vegetables", "potatoes", "salad greens", "eggs or beans"];
  return `Grocery List
${base.map((item) => `- ${item}`).join("\n")}

Based on meal plan:
${plan.length ? plan.map((meal) => `- ${meal.food}`).join("\n") : "- Generate a meal plan first for a more specific list."}`;
}

function recipeGenerator(ingredientsText) {
  const ingredients = ingredientsText.replace(/recipe|ingredients|make|from/gi, "").trim() || "eggs, rice, vegetables";
  return `Recipe Idea
Ingredients: ${ingredients}

High-Protein Bowl:
1. Cook your main carb, such as rice, potatoes, or oats.
2. Add a protein source from your ingredients.
3. Add vegetables or fruit for fiber.
4. Season with spices, lemon, yogurt sauce, or a small amount of olive oil.
5. Keep the portion matched to your calorie target.`;
}

function recoveryAdvisor(message = "") {
  const logs = getLogs();
  const last = logs.checkins[logs.checkins.length - 1] || {};
  const sleep = number(last.sleep, message.includes("5 hours") ? 5 : 7);
  const soreness = number(last.soreness, /sore|pain/.test(message.toLowerCase()) ? 7 : 4);
  const energy = number(last.energy, 6);
  const advice = sleep < 6 || soreness >= 7 || energy <= 4
    ? "Use recovery today: walking, mobility, light stretching, and an early night."
    : "You can train normally, but warm up well and stop if pain appears.";
  return `Sleep and Recovery Advisor
- Sleep: ${sleep || "not logged"} hours
- Soreness: ${soreness || "not logged"}/10
- Energy: ${energy || "not logged"}/10
- Recommendation: ${advice}`;
}

function weeklyProgress() {
  const logs = getLogs();
  const meals = logs.meals.filter(inLastWeek);
  const workouts = logs.workouts.filter(inLastWeek);
  const weights = logs.weights.filter(inLastWeek);
  const checkins = logs.checkins.filter(inLastWeek);
  const firstWeight = weights[0]?.weight;
  const lastWeight = weights[weights.length - 1]?.weight;
  const weightChange = firstWeight && lastWeight ? +(lastWeight - firstWeight).toFixed(1) : 0;
  const streak = calculateStreak(logs.workouts);
  const status = workouts.length >= 3 && meals.length >= 5 ? "on track" : "needs adjustment";
  const recommendation = status === "on track"
    ? "Keep the same plan next week and increase one exercise slightly."
    : "Log meals more consistently and aim for at least 3 workouts next week.";
  return `Weekly Progress
- Workouts completed: ${workouts.length}
- Meals logged: ${meals.length}
- Weight change: ${weightChange} kg
- Check-ins: ${checkins.length}
- Streak: ${streak} day(s)
- Status: ${status}
- Recommendation: ${recommendation}`;
}

function calculateStreak(workouts) {
  const dates = new Set(workouts.map((item) => item.date.slice(0, 10)));
  let streak = 0;
  const date = new Date();
  while (dates.has(date.toISOString().slice(0, 10))) {
    streak += 1;
    date.setDate(date.getDate() - 1);
  }
  return streak;
}

function logMeal(text) {
  const estimate = estimateFood(text);
  const meals = load(STORAGE_KEYS.meals, []);
  meals.push({ text, ...estimate, date: today() });
  save(STORAGE_KEYS.meals, meals);
  updateProteinAchievement();
  return `Meal logged: ${text}
- Calories: ${estimate.calories} kcal
- Protein: ${estimate.protein}g
- Carbs: ${estimate.carbs}g
- Fat: ${estimate.fat}g
- Healthier alternative: add vegetables, choose grilled protein, and control sauces or fried extras.`;
}

function logWorkout(text) {
  const workouts = load(STORAGE_KEYS.workouts, []);
  workouts.push({ text, date: today() });
  save(STORAGE_KEYS.workouts, workouts);
  render();
  return `Workout logged: ${text}
Nice work. Hydrate, eat protein, and watch recovery before your next hard session.`;
}

function logWeight(value) {
  const weights = load(STORAGE_KEYS.weights, []);
  weights.push({ weight: number(value), date: today() });
  save(STORAGE_KEYS.weights, weights);
  render();
  return "Weight logged.";
}

function updateProteinAchievement() {
  const metrics = calculateMetrics();
  if (!metrics) return;
  const todayMeals = load(STORAGE_KEYS.meals, []).filter((meal) => meal.date.slice(0, 10) === todayKey());
  const protein = todayMeals.reduce((sum, meal) => sum + number(meal.protein), 0);
  if (protein >= metrics.protein) {
    localStorage.setItem("fitai_protein_hit", "true");
  }
}

function saveCheckin() {
  const checkins = load(STORAGE_KEYS.checkins, []);
  checkins.push({
    sleep: number($("sleepInput").value),
    mood: number($("moodInput").value),
    soreness: number($("sorenessInput").value),
    energy: number($("energyInput").value),
    date: today()
  });
  save(STORAGE_KEYS.checkins, checkins);
  render();
  showTool(recoveryAdvisor());
}

function coachReply(message) {
  const lower = message.toLowerCase();
  const warnings = safetyCheck(message);
  let reply = "";
  const needsProfile = /lose weight|gain muscle|maintain|calorie|macro|bmr|tdee|workout|plan|routine|meal plan|diet plan|what should i eat|water|hydration/.test(lower);
  if (needsProfile && !isProfileComplete()) {
    return "Complete your profile first so FitAI can personalize calories, workouts, meals, and hydration for you.";
  }
  if (/ate|meal|food|chicken|rice|pizza|burger|pasta|salad/.test(lower)) {
    reply = logMeal(message);
  } else if (/completed|workout done|leg day|push day|pull day|trained|exercise/.test(lower)) {
    reply = logWorkout(message);
  } else if (/progress|summary|dashboard|streak/.test(lower)) {
    reply = weeklyProgress();
  } else if (/sleep|sore|soreness|tired|recovery|pain/.test(lower)) {
    reply = recoveryAdvisor(message);
  } else if (/grocery|shopping/.test(lower)) {
    reply = groceryList();
  } else if (/recipe|ingredients|cook/.test(lower)) {
    reply = recipeGenerator(message);
  } else if (/water|hydration|drink/.test(lower)) {
    reply = hydrationCalculator();
  } else if (/meal plan|diet plan|what should i eat/.test(lower)) {
    reply = generateMealPlan();
  } else if (/lose weight|gain muscle|maintain|calorie|macro|bmr|tdee/.test(lower)) {
    reply = `${formatMetrics()}\n\n${generateWorkoutPlan()}`;
  } else if (/workout|plan|routine/.test(lower)) {
    reply = generateWorkoutPlan();
  } else {
    reply = "I can help with calories, macros, workouts, meals, logs, progress, hydration, grocery lists, recipes, and recovery. Try asking for a meal plan or weekly progress.";
  }
  return warnings.length ? `Safety note:\n- ${warnings.join("\n- ")}\n\n${reply}` : reply;
}

function formatMetrics() {
  const metrics = calculateMetrics();
  if (!metrics) {
    return "Please complete your profile first so I can calculate your targets.";
  }
  return `Calories and Macros
- BMI: ${metrics.bmi}
- BMR: ${metrics.bmr} kcal
- TDEE / maintenance: ${metrics.tdee} kcal
- Goal calorie target: ${metrics.calorieTarget} kcal
- Protein target: ${metrics.protein}g
- Carbs target: ${metrics.carbs}g
- Fat target: ${metrics.fat}g
- Recommended weekly weight change: ${metrics.weeklyChange}`;
}

function addChat(role, text) {
  const chat = load(STORAGE_KEYS.chat, []);
  chat.push({ role, text, date: today() });
  save(STORAGE_KEYS.chat, chat);
  renderChat();
}

function renderChat() {
  const messages = load(STORAGE_KEYS.chat, []);
  $("chatMessages").innerHTML = messages.map((msg) => (
    `<div class="msg ${msg.role}">${escapeHtml(msg.text)}</div>`
  )).join("");
  $("chatMessages").scrollTop = $("chatMessages").scrollHeight;
}

function escapeHtml(text) {
  return text.replace(/[&<>"']/g, (char) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#039;"
  }[char]));
}

function showTool(text) {
  $("toolOutput").textContent = text;
  render();
}

function renderDashboard() {
  const metrics = calculateMetrics();
  const logs = getLogs();
  const workouts = logs.workouts.filter(inLastWeek).length;
  const cards = [
    ["BMI", metrics ? metrics.bmi : "Add profile"],
    ["Calorie Target", metrics ? `${metrics.calorieTarget}` : "-"],
    ["Protein", metrics ? `${metrics.protein}g` : "-"],
    ["Workouts", workouts],
    ["Streak", `${calculateStreak(logs.workouts)} day(s)`],
    ["Weekly Progress", workouts >= 3 ? "On track" : "Needs logs"]
  ];
  $("dashboardCards").innerHTML = cards.map(([label, value]) => (
    `<article class="card"><span>${label}</span><strong>${value}</strong></article>`
  )).join("");
  $("weeklySummary").textContent = weeklyProgress();
  renderProfileBanner();
  renderDailyRecommendation();
  renderOnboarding();
  renderWorkoutChecklist();
  renderMealDiary();
  renderCharts();
  renderAchievements();
  renderReport();
}

function renderDailyRecommendation() {
  const metrics = calculateMetrics();
  const logs = getLogs();
  const workoutsThisWeek = logs.workouts.filter(inLastWeek).length;
  const workout = workoutsThisWeek % 2 === 0 ? "full body strength" : "cardio and mobility";
  const water = hydrationCalculator().match(/Daily water: ([\d]+)/)?.[1] || "2500";
  const protein = metrics ? `${metrics.protein}g protein` : "complete profile for protein target";
  $("dailyRecommendation").innerHTML = `<strong>Today</strong>${workout} + ${(number(water) / 1000).toFixed(1)}L water + ${protein}`;
}

function renderOnboarding() {
  const profile = getProfile();
  const hasPlan = load(STORAGE_KEYS.workoutChecklist, []).length > 0 || load(STORAGE_KEYS.mealPlan, []).length > 0;
  const steps = [
    ["1", "Profile", profile.age && profile.height && profile.weight],
    ["2", "Goal", profile.goal],
    ["3", "Training", profile.fitnessLevel && profile.place],
    ["4", "Generate plan", hasPlan]
  ];
  $("onboarding").innerHTML = `<div class="section-title"><h2>First-Time Setup</h2><span>4 quick steps</span></div>
    <div class="steps">${steps.map(([num, label, done]) => (
      `<div class="step ${done ? "done" : ""}"><span>Step ${num}</span><strong>${label}</strong></div>`
    )).join("")}</div>`;
}

function renderWorkoutChecklist() {
  const checklist = load(STORAGE_KEYS.workoutChecklist, []);
  if (!checklist.length) {
    $("workoutChecklist").innerHTML = "<p>Generate a workout plan to create today's checklist.</p>";
    return;
  }
  $("workoutChecklist").innerHTML = checklist.map((item, index) => `
    <div class="exercise-row">
      <div class="exercise-top">
        <strong>${escapeHtml(item.name)}</strong>
        <label><input type="checkbox" data-check="${index}" ${item.skipped ? "checked" : ""}> Skipped</label>
      </div>
      <div class="exercise-controls">
        <label>Completed sets <input type="number" min="0" max="6" value="${item.completedSets}" data-sets="${index}"></label>
        <label>Difficulty
          <select data-difficulty="${index}">
            <option ${item.difficulty === "easy" ? "selected" : ""}>easy</option>
            <option ${item.difficulty === "medium" ? "selected" : ""}>medium</option>
            <option ${item.difficulty === "hard" ? "selected" : ""}>hard</option>
          </select>
        </label>
        <button data-complete="${index}">Save Exercise</button>
      </div>
    </div>
  `).join("");
  document.querySelectorAll("[data-complete]").forEach((button) => {
    button.addEventListener("click", () => updateExercise(Number(button.dataset.complete)));
  });
}

function updateExercise(index) {
  const checklist = load(STORAGE_KEYS.workoutChecklist, []);
  checklist[index].completedSets = number(document.querySelector(`[data-sets="${index}"]`).value);
  checklist[index].difficulty = document.querySelector(`[data-difficulty="${index}"]`).value;
  checklist[index].skipped = document.querySelector(`[data-check="${index}"]`).checked;
  save(STORAGE_KEYS.workoutChecklist, checklist);
  const doneCount = checklist.filter((item) => item.completedSets > 0 && !item.skipped).length;
  if (doneCount >= Math.ceil(checklist.length / 2)) {
    logWorkout(`Checklist workout: ${doneCount}/${checklist.length} exercises completed`);
  }
  render();
}

function renderMealDiary() {
  const meals = load(STORAGE_KEYS.meals, []);
  const todayMeals = meals.filter((meal) => meal.date.slice(0, 10) === todayKey());
  const totals = todayMeals.reduce((sum, meal) => ({
    calories: sum.calories + number(meal.calories),
    protein: sum.protein + number(meal.protein)
  }), { calories: 0, protein: 0 });
  $("mealDiary").innerHTML = `
    <div class="diary-row"><strong>Today totals</strong><span>${totals.calories} kcal | ${totals.protein}g protein</span></div>
    ${todayMeals.slice(-5).reverse().map((meal) => `
      <div class="diary-row">
        <div class="diary-top"><strong>${escapeHtml(meal.text)}</strong><span>${meal.calories} kcal</span></div>
        <span>P ${meal.protein}g | C ${meal.carbs}g | F ${meal.fat}g</span>
      </div>
    `).join("") || "<p>No meals logged today.</p>"}`;
}

function renderCharts() {
  const logs = getLogs();
  const meals = logs.meals.filter(inLastWeek);
  const workouts = logs.workouts.filter(inLastWeek);
  const checkins = logs.checkins.filter(inLastWeek);
  const calories = meals.reduce((sum, meal) => sum + number(meal.calories), 0);
  const avgSleep = checkins.length ? checkins.reduce((sum, item) => sum + number(item.sleep), 0) / checkins.length : 0;
  const chartItems = [
    ["Weekly calories", calories, 14000],
    ["Workouts", workouts.length, 5],
    ["Check-ins", checkins.length, 7],
    ["Avg sleep", avgSleep.toFixed(1), 8]
  ];
  $("charts").innerHTML = chartItems.map(([label, value, max]) => {
    const width = Math.min((number(value) / max) * 100, 100).toFixed(0);
    return `<div class="chart-row"><div class="diary-top"><strong>${label}</strong><span>${value}</span></div><div class="bar-track"><div class="bar-fill" style="--w:${width}%"></div></div></div>`;
  }).join("");
}

function renderAchievements() {
  const logs = getLogs();
  const achievements = [
    ["3-day workout streak", calculateStreak(logs.workouts) >= 3],
    ["Protein goal hit", localStorage.getItem("fitai_protein_hit") === "true"],
    ["7 meals logged", logs.meals.length >= 7],
    ["First report exported", localStorage.getItem(STORAGE_KEYS.exportedReport) === "true"]
  ];
  $("achievements").innerHTML = achievements.map(([label, done]) => (
    `<div class="achievement ${done ? "done" : ""}"><strong>${done ? "✓" : "○"}</strong><span>${label}</span></div>`
  )).join("");
}

function renderReport() {
  const metrics = calculateMetrics();
  const logs = getLogs();
  const profile = getProfile();
  $("reportContent").innerHTML = `
    <h3>Summary</h3>
    <p>${weeklyProgress()}</p>
    <h3>Stats</h3>
    <p>BMI: ${metrics ? metrics.bmi : "-"} | Calories: ${metrics ? metrics.calorieTarget : "-"} | Protein: ${metrics ? metrics.protein : "-"}g</p>
    <h3>Recommendation</h3>
    <p>${logs.workouts.filter(inLastWeek).length >= 3 ? "Keep the plan steady and progress one exercise next week." : "Aim for 3 workouts and 5 logged meals next week."}</p>
    <h3>Next Week Plan</h3>
    <p>${profile.fitnessLevel || "Beginner"} ${profile.place || "home"} plan: 3 strength sessions, 1 cardio day, 1 mobility or recovery day. Add 1-2 reps or a small weight increase if recovery is good.</p>
  `;
}

function renderProfileForm() {
  const profile = getProfile();
  Object.keys(profile).forEach((key) => {
    if ($(key)) {
      $(key).value = profile[key];
    }
  });
}

function render() {
  renderDashboard();
  renderChat();
}

function initEvents() {
  $("profileForm").addEventListener("submit", (event) => {
    event.preventDefault();
    setProfile({
      age: $("age").value,
      height: $("height").value,
      weight: $("weight").value,
      gender: $("gender").value,
      goal: $("goal").value,
      activity: $("activity").value,
      fitnessLevel: $("fitnessLevel").value,
      place: $("place").value,
      restrictions: $("restrictions").value,
      budget: $("budget").value
    });
    renderProfileBanner("Profile saved successfully. Your dashboard and tools are updated.");
    showTool("Profile saved successfully. Your dashboard and tools are updated.");
  });

  $("chatForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    const message = $("chatInput").value.trim();
    if (!message) return;
    $("chatInput").value = "";
    addChat("user", message);
    addChat("bot", "Thinking...");
    try {
      const reply = await askFitAI(message);
      const chat = load(STORAGE_KEYS.chat, []);
      chat[chat.length - 1].text = reply;
      save(STORAGE_KEYS.chat, chat);
    } catch (error) {
      const chat = load(STORAGE_KEYS.chat, []);
      chat[chat.length - 1].text = `I could not reach the FitAI API. ${error.message}`;
      save(STORAGE_KEYS.chat, chat);
    }
    render();
  });

  document.querySelectorAll("[data-prompt]").forEach((button) => {
    button.addEventListener("click", async () => {
      const message = button.dataset.prompt;
      addChat("user", message);
      addChat("bot", "Thinking...");
      try {
        const reply = await askFitAI(message);
        const chat = load(STORAGE_KEYS.chat, []);
        chat[chat.length - 1].text = reply;
        save(STORAGE_KEYS.chat, chat);
      } catch (error) {
        const chat = load(STORAGE_KEYS.chat, []);
        chat[chat.length - 1].text = `I could not reach the FitAI API. ${error.message}`;
        save(STORAGE_KEYS.chat, chat);
      }
      render();
    });
  });

  $("logMealBtn").addEventListener("click", () => showTool(logMeal($("mealInput").value || "meal")));
  $("logWorkoutBtn").addEventListener("click", () => showTool(logWorkout($("workoutInput").value || "workout")));
  $("logWeightBtn").addEventListener("click", () => showTool(logWeight($("weightInput").value)));
  $("checkinBtn").addEventListener("click", saveCheckin);
  $("calcBtn").addEventListener("click", () => requireProfile() && showTool(formatMetrics()));
  $("workoutBtn").addEventListener("click", () => requireProfile() && showTool(generateWorkoutPlan()));
  $("mealPlanBtn").addEventListener("click", () => requireProfile() && showTool(generateMealPlan()));
  $("hydrationBtn").addEventListener("click", () => requireProfile() && showTool(hydrationCalculator()));
  $("groceryBtn").addEventListener("click", () => requireProfile() && showTool(groceryList()));
  $("recoveryBtn").addEventListener("click", () => showTool(recoveryAdvisor()));
  $("printBtn").addEventListener("click", () => {
    save(STORAGE_KEYS.exportedReport, "true");
    renderAchievements();
    window.print();
  });
  $("themeBtn").addEventListener("click", () => {
    const next = document.body.classList.contains("dark") ? "light" : "dark";
    save(STORAGE_KEYS.theme, next);
    applyTheme();
  });
  $("resetBtn").addEventListener("click", () => {
    if (confirm("Clear all local FitAI Coach data?")) {
      Object.values(STORAGE_KEYS).forEach((key) => localStorage.removeItem(key));
      location.reload();
    }
  });
}

function applyTheme() {
  const theme = load(STORAGE_KEYS.theme, "light");
  document.body.classList.toggle("dark", theme === "dark");
  $("themeBtn").textContent = theme === "dark" ? "Light Mode" : "Dark Mode";
}

renderProfileForm();
applyTheme();
if (!localStorage.getItem(STORAGE_KEYS.chat)) {
  save(STORAGE_KEYS.chat, [{
    role: "bot",
    text: "Hi, I am FitAI. Complete your profile, then ask me for calories, workouts, meals, progress, hydration, recipes, or recovery advice.",
    date: today()
  }]);
}
initEvents();
render();
