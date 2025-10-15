from flask import Flask, render_template, request, redirect, url_for, jsonify
import sqlite3
from datetime import datetime, timedelta
import random
from openai import OpenAI
import os

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

app = Flask(__name__)
@app.template_filter('zip')
def zip_filter(a, b):
    return zip(a, b)

# --- Database Setup ---
conn = sqlite3.connect("habits.db", check_same_thread=False)
cursor = conn.cursor()

targets = {"water": 8, "exercise": 3, "sleep": 8, "study": 4}
HABITS = list(targets.keys())

# --- Create Table with user support ---
cursor.execute("""
CREATE TABLE IF NOT EXISTS habits (
    date TEXT,
    user_id TEXT,
    water INTEGER DEFAULT 0,
    exercise INTEGER DEFAULT 0,
    sleep INTEGER DEFAULT 0,
    study INTEGER DEFAULT 0,
    streak INTEGER DEFAULT 0,
    PRIMARY KEY (date, user_id)
)
""")
conn.commit()

# --- Helper Functions ---
def init_today(user_id="default_user"):
    today = datetime.today().strftime("%Y-%m-%d")
    cursor.execute("SELECT * FROM habits WHERE user_id=? AND date=?", (user_id, today))
    if cursor.fetchone() is None:
        cursor.execute("INSERT INTO habits VALUES (?, ?, 0, 0, 0, 0, 0)", (today, user_id))
        conn.commit()

def get_today_habits(user_id="default_user"):
    today = datetime.today().strftime("%Y-%m-%d")
    cursor.execute("SELECT water, exercise, sleep, study, streak FROM habits WHERE user_id=? AND date=?", (user_id, today))
    row = cursor.fetchone()
    return row if row else (0, 0, 0, 0, 0)

def update_habit(habit, amount, user_id="default_user"):
    today = datetime.today().strftime("%Y-%m-%d")
    if habit not in HABITS:
        return
    cursor.execute(f"UPDATE habits SET {habit} = {habit} + ? WHERE user_id=? AND date=?", (amount, user_id, today))
    conn.commit()

def get_last_n_days(user_id="default_user", n=30):
    today = datetime.today().date()
    start_date = today - timedelta(days=n-1)
    cursor.execute("""
        SELECT date, water, exercise, sleep, study, streak
        FROM habits
        WHERE user_id=? AND date >= ?
        ORDER BY date ASC
    """, (user_id, start_date.strftime("%Y-%m-%d")))
    return cursor.fetchall()

def calculate_calendar_and_streak(user_id="default_user", days=30):
    records = get_last_n_days(user_id, days)
    today = datetime.today().date()
    start_date = today - timedelta(days=days-1)
    records_dict = {datetime.strptime(d, "%Y-%m-%d").date(): (w, e, s, st, streak) for d, w, e, s, st, streak in records}

    calendar = []
    current_streak = 0
    best_streak = 0
    last_day = None

    for i in range(days):
        day = start_date + timedelta(days=i)
        if day in records_dict:
            w, e, s, st, _ = records_dict[day]
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

def update_streak_for_today(user_id="default_user"):
    today = datetime.today().strftime("%Y-%m-%d")
    cursor.execute("SELECT water, exercise, sleep, study FROM habits WHERE user_id=? AND date=?", (user_id, today))
    w, e, s, st = cursor.fetchone()
    if w >= targets["water"] and e >= targets["exercise"] and s >= targets["sleep"] and st >= targets["study"]:
        yesterday = (datetime.today() - timedelta(days=1)).strftime("%Y-%m-%d")
        cursor.execute("SELECT streak FROM habits WHERE user_id=? AND date=?", (user_id, yesterday))
        row = cursor.fetchone()
        yesterday_streak = row[0] if row else 0
        today_streak = yesterday_streak + 1
    else:
        today_streak = 0
    cursor.execute("UPDATE habits SET streak=? WHERE user_id=? AND date=?", (today_streak, user_id, today))
    conn.commit()

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

# --- Leaderboard ---
def get_leaderboard():
    cursor.execute("""
        SELECT user_id, MAX(streak) as best_streak
        FROM habits
        GROUP BY user_id
        ORDER BY best_streak DESC
        LIMIT 5
    """)
    return cursor.fetchall()

# --- Routes ---
@app.route("/", methods=["GET", "POST"])
def index():
    # For demo, we'll use a fixed user_id
    user_id = request.args.get("user", "User1")
    init_today(user_id)

    if request.method == "POST":
        habit = request.form.get("habit")
        amount = int(request.form.get("amount"))
        if habit in targets:
            update_habit(habit, amount, user_id)
            update_streak_for_today(user_id)
        return redirect(url_for("index", user=user_id))

    habits = get_today_habits(user_id)
    calendar, curr_streak, best_streak = calculate_calendar_and_streak(user_id)
    habits_list = list(zip(targets.keys(), habits[:4]))  # only habit amounts

    compliment = get_compliment() if all(h >= targets[h_name] for h, h_name in zip(habits[:4], HABITS)) else None

    leaderboard = get_leaderboard()

    return render_template(
        "index.html",
        habits_list=habits_list,
        targets=targets,
        calendar=calendar,
        curr_streak=curr_streak,
        best_streak=best_streak,
        compliment=compliment,
        leaderboard=leaderboard
    )

# --- API for Chart ---
@app.route("/chart-data")
def chart_data():
    user_id = request.args.get("user", "User1")
    records = get_last_n_days(user_id, 7)
    labels = [datetime.strptime(d, "%Y-%m-%d").strftime("%b %d") for d, *_ in records]
    water = [w for d, w, e, s, st, streak in records]
    exercise = [e for d, w, e, s, st, streak in records]
    sleep = [s for d, w, e, s, st, streak in records]
    study = [st for d, w, e, s, st, streak in records]
    return jsonify({"labels": labels, "water": water, "exercise": exercise, "sleep": sleep, "study": study})

# --- AI Feedback ---
@app.route("/generate_ai_feedback")
def generate_ai_feedback():
    user_id = request.args.get("user", "User1")
    records = get_last_n_days(user_id, 7)
    if not records:
        return jsonify({"error": "No data found for the last 7 days"}), 400

    summary = "\n".join([f"{d}: Water={w}, Exercise={e}, Sleep={s}, Streak={st}" for d, w, e, s, st, _ in records])
    prompt = f"""
    You are a wellness coach analyzing habit data.
    Here’s {user_id}'s last 7 days:
    {summary}

    Provide a motivating summary (≤100 words):
    1. Wins this week.
    2. Areas to improve.
    3. One friendly tip.
    """
    try:
        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
        )
        feedback = completion.choices[0].message.content.strip()
        return jsonify({"feedback": feedback})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/leaderboard")
def leaderboard():
    data = [("2428cs594", 1)]  # example
    return render_template("leaderboard.html", leaderboard=data)


if __name__ == "__main__":
    app.run(debug=True)
