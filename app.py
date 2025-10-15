
from flask import Flask, render_template, request, redirect, url_for, jsonify
import sqlite3
from datetime import datetime, timedelta
import random
from openai import OpenAI
import os

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# --- Flask App ---
app = Flask(__name__)
@app.template_filter('zip')
def zip_filter(a, b):
    return zip(a, b)

# --- Database Setup ---
conn = sqlite3.connect("habits.db", check_same_thread=False)
cursor = conn.cursor()

targets = {"water": 8, "exercise": 3, "sleep": 8, "study": 4}
HABITS = list(targets.keys())

# --- Create Table if not exists ---
cursor.execute("""
CREATE TABLE IF NOT EXISTS habits (
    date TEXT PRIMARY KEY,
    water INTEGER DEFAULT 0,
    exercise INTEGER DEFAULT 0,
    sleep INTEGER DEFAULT 0,
    study INTEGER DEFAULT 0
)
""")
conn.commit()
from datetime import datetime, timedelta
import sqlite3

def get_last_7_days_summary():
    conn = sqlite3.connect("habits.db")
    c = conn.cursor()
    start_date = (datetime.today() - timedelta(days=6)).strftime("%Y-%m-%d")

    c.execute("""
        SELECT date, water, exercise, sleep, streak
        FROM habits
        WHERE date >= ?
        ORDER BY date ASC
    """, (start_date,))
    rows = c.fetchall()
    conn.close()

    data = []
    for date_str, water, exercise, sleep, streak in rows:
        data.append({
            "date": date_str,
            "water": water,
            "exercise": exercise,
            "sleep": sleep,
            "streak": streak
        })
    return data

# --- Helper Functions ---
def init_today():
    today = datetime.today().strftime("%Y-%m-%d")
    cursor.execute("SELECT * FROM habits WHERE date=?", (today,))
    if cursor.fetchone() is None:
        cursor.execute("INSERT INTO habits VALUES (?, 0, 0, 0, 0, 0)", (today,))
        conn.commit()

def get_today_habits():
    today = datetime.today().strftime("%Y-%m-%d")
    cursor.execute("SELECT water, exercise, sleep, study FROM habits WHERE date=?", (today,))
    return cursor.fetchone()

def update_habit(habit, amount):
    today = datetime.today().strftime("%Y-%m-%d")
    if habit not in HABITS:
        return
    cursor.execute(f"UPDATE habits SET {habit} = {habit} + ? WHERE date=?", (amount, today))
    conn.commit()

def get_last_n_days(n=30):
    today = datetime.today().date()
    start_date = today - timedelta(days=n-1)
    cursor.execute("SELECT date, water, exercise, sleep, study FROM habits WHERE date >= ? ORDER BY date ASC", (start_date.strftime("%Y-%m-%d"),))
    return cursor.fetchall()

def calculate_calendar_and_streak(days=30):
    records = get_last_n_days(days)
    today = datetime.today().date()
    start_date = today - timedelta(days=days-1)
    records_dict = {datetime.strptime(d, "%Y-%m-%d").date(): (w, e, s, st) for d, w, e, s, st in records}

    calendar = []
    current_streak = 0
    best_streak = 0
    last_day = None

    for i in range(days):
        day = start_date + timedelta(days=i)
        if day in records_dict:
            w, e, s, st = records_dict[day]
            if w >= targets["water"] and e >= targets["exercise"] and s >= targets["sleep"] and st >= targets["study"]:
                symbol = "🟩"
                if last_day and (day - last_day).days == 1:
                    current_streak += 1
                else:
                    current_streak = 1
                best_streak = max(best_streak, current_streak)
            else:
                symbol = "⬜"
                current_streak = 0
        else:
            symbol = "⬜"
            current_streak = 0
        last_day = day
        calendar.append(symbol)

    return "".join(calendar), current_streak, best_streak

# --- New helpers for "progress" detection ---
def last_nonzero_date_for(habit):
    """Return the most recent date string (YYYY-MM-DD) where habit > 0 or None."""
    if habit not in HABITS:
        return None
    # safe to use f-string because habit is validated above
    cursor.execute(f"SELECT date FROM habits WHERE {habit} > 0 ORDER BY date DESC LIMIT 1")
    row = cursor.fetchone()
    return row[0] if row else None

def days_since_last_progress(habit):
    ld = last_nonzero_date_for(habit)
    if ld is None:
        return None
    last = datetime.strptime(ld, "%Y-%m-%d").date()
    return (datetime.today().date() - last).days

# --- Compliment generator ---
def get_compliment():
    compliments = [
        "Amazing job! You're building a great habit 👏",
        "Consistency is your superpower 💪",
        "Keep it up — success is built one day at a time 🌱",
        "You're on fire today! 🔥",
        "Well done! Discipline always pays off 🌟",
        "You're becoming the best version of yourself 🚀",
        "Outstanding! You crushed your goals today 🏆"
    ]
    return random.choice(compliments)
def update_streak_for_today():
    today = datetime.today().strftime("%Y-%m-%d")
    cursor.execute("SELECT water, exercise, sleep, study FROM habits WHERE date=?", (today,))
    w, e, s, st = cursor.fetchone()
    
    # Check if all targets met
    if w >= targets["water"] and e >= targets["exercise"] and s >= targets["sleep"] and st >= targets["study"]:
        # get yesterday's streak
        yesterday = (datetime.today() - timedelta(days=1)).strftime("%Y-%m-%d")
        cursor.execute("SELECT streak FROM habits WHERE date=?", (yesterday,))
        row = cursor.fetchone()
        yesterday_streak = row[0] if row else 0
        today_streak = yesterday_streak + 1
    else:
        today_streak = 0
    
    # update today streak
    cursor.execute("UPDATE habits SET streak=? WHERE date=?", (today_streak, today))
    conn.commit()

# --- API Route for Chart.js ---
@app.route("/chart-data")
def chart_data():
    records = get_last_n_days(7)  # last 7 days for chart
    labels = [datetime.strptime(d, "%Y-%m-%d").strftime("%b %d") for d, *_ in records]
    water = [w for d, w, e, s, st in records]
    exercise = [e for d, w, e, s, st in records]
    sleep = [s for d, w, e, s, st in records]
    study = [st for d, w, e, s, st in records]

    return jsonify({
        "labels": labels,
        "water": water,
        "exercise": exercise,
        "sleep": sleep,
        "study": study
    })

# --- New API: status for client-side polling ---
@app.route("/status")
def status():
    """Return JSON with:
       - completed_today (bool)
       - incomplete_habits (list)
       - days_since_progress for each habit (or null)
       - compliment if completed
    """
    init_today()
    habits = get_today_habits()
    completed_today = all([
        habits[0] >= targets["water"],
        habits[1] >= targets["exercise"],
        habits[2] >= targets["sleep"],
        habits[3] >= targets["study"]
    ])
    incomplete = []
    for i, h in enumerate(HABITS):
        if habits[i] < targets[h]:
            incomplete.append({"habit": h, "value": habits[i], "target": targets[h]})

    dsp = {h: days_since_last_progress(h) for h in HABITS}
    compliment = get_compliment() if completed_today else None

    return jsonify({
        "completed_today": completed_today,
        "incomplete_habits": incomplete,
        "days_since_progress": dsp,
        "compliment": compliment
    })

# --- Main Route ---
@app.route("/", methods=["GET", "POST"])
def index():
    init_today()
    
    if request.method == "POST":
        habit = request.form.get("habit")
        amount = int(request.form.get("amount"))
        if habit in targets:
            update_habit(habit, amount)
        return redirect(url_for("index"))

    habits = get_today_habits()
    calendar, curr_streak, best_streak = calculate_calendar_and_streak()
    habits_list = list(zip(targets.keys(), habits))  # Prepare list for template

    compliment = None
    if all([
        habits[0] >= targets["water"],
        habits[1] >= targets["exercise"],
        habits[2] >= targets["sleep"],
        habits[3] >= targets["study"]
    ]):
        compliment = get_compliment()

    return render_template(
        "index.html",
        habits_list=habits_list,
        targets=targets,
        calendar=calendar,
        curr_streak=curr_streak,
        best_streak=best_streak,
        compliment=compliment
    )
@app.route("/generate_ai_feedback")
def generate_ai_feedback():
    # --- Get last 7 days’ data ---
    data = get_last_7_days_summary()
    if not data:
        return jsonify({"error": "No data found for the last 7 days"}), 400

    # --- Prepare a compact summary ---
    summary_lines = []
    for row in data:
        summary_lines.append(
            f"{row['date']}: Water={row['water']}, Exercise={row['exercise']}, Sleep={row['sleep']}, Streak={row['streak']}"
        )
    summary_text = "\n".join(summary_lines)

    # --- Send to ChatGPT ---
    prompt = f"""
    You are a wellness coach analyzing habit data.
    Here’s the user’s last 7 days of activity:
    {summary_text}

    Please provide a short, motivating summary (≤100 words) covering:
    1. What went well this week.
    2. Areas to improve.
    3. One friendly tip for next week.
    Make it sound like a personal coach giving gentle feedback.
    """

    try:
        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
        )
        feedback = completion.choices[0].message.content.strip()
        return jsonify({"feedback": feedback})
    except Exception as e:
        print("AI feedback error:", e)
        return jsonify({"error": str(e)}), 500

# --- Run App ---
if __name__ == "__main__":
    app.run(debug=True)
