from flask import Flask, render_template, request, redirect, url_for, flash
from datetime import datetime, timedelta
import pytz
import requests
import os
import sqlite3

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev_secret")

# 🔹 Telegram config
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")
DB_PATH = "app.db"


#def send_telegram_msg(message):
#    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
#    data = {"chat_id": CHAT_ID, "text": message, "parse_mode": "HTML"}
#    requests.post(url, data=data)


def get_conn():
    return sqlite3.connect(DB_PATH)

# Function to insert a new activity
def insert_activity(data):
    try:
        conn = get_conn()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO activities (
                date, group_name, activity_type, time, occasion, place,
                leaders_count, jawele_count, kashefe_count, ashbele_count,
                bara3em_count, non_scouts_count, paragraphs, cost
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            data["date"],
            data["group"],
            data["activity_type"],
            data["time"],
            data["occasion"],
            data["place"],
            data["leaders_count"],
            data["jawele_count"],
            data["kashefe_count"],
            data["ashbele_count"],
            data["bara3em_count"],
            data["non_scouts_count"],
            "\n".join(data["paragraphs"]),
            data["cost"]
        ))
        conn.commit()
        print("✅ Insert successful")
    except Exception as e:
        print("❌ DB Insert Error:", e)
    finally:
        conn.close()



# Function to update an existing activity TODO
def update_activity(activity_id, data):
    ...

def send_telegram_file(message, photo):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
    data = {"chat_id": CHAT_ID, "caption": message, "parse_mode": "HTML"}
    files = {"photo": photo}
    requests.post(url, data=data, files=files)

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        form_data = {
            "date": request.form.get("date"),
            "group": request.form.get("group"),
            "activity_type": request.form.get("activity_type"),
            "place": request.form.get("place"),
            "time": request.form.get("time"),
            "leaders_count": int(request.form.get("leaders_count", 0)),
            "jawele_count": int(request.form.get("jawele_count", 0)),
            "kashefe_count": int(request.form.get("kashefe_count", 0)),
            "ashbele_count": int(request.form.get("ashbele_count", 0)),
            "bara3em_count": int(request.form.get("bara3em_count", 0)),
            "non_scouts_count": int(request.form.get("non_scouts_count", 0)),
            "occasion": request.form.get("occasion"),
            "paragraphs": request.form.getlist("paragraphs[]"),
            "cost": int(request.form.get("cost", 0))

        }

        # Validation
        if not form_data["paragraphs"] or all(not p.strip() for p in form_data["paragraphs"]):
            flash("يجب إضافة فقرة واحدة على الأقل.", "error")
            return redirect(url_for("index"))

        # Insert the activity into the database
        insert_activity(form_data)

        ## Send the Telegram message
        #msg = f"📌 <b>نموذج النشاط تم الإرسال</b>\n"
        #for k, v in form_data.items():
        #    if k == "الفقرات المنفذة":
        #        paragraphs = "\n".join([f"- {p}" for p in v if p.strip()])
        #        msg += f"{k}:\n{paragraphs}\n"
        #    else:
        #        msg += f"{k}: {v}\n"
#
        #send_telegram_msg(msg)

        files = request.files.getlist("files[]")
        if files and any(f.filename for f in files):
            for file in files:
                if file and file.filename:
                    send_telegram_file(request.form.get("activity_type"), file)

        return redirect(url_for("index"))

    # Use Lebanon local date (Asia/Beirut)
    ttz = pytz.timezone("Asia/Beirut")
    lebanon_time = datetime.now(ttz).date()
    return render_template("index.html", today=lebanon_time)

@app.route("/activities")
def activities():
    # Default date ranges
    today = datetime.utcnow().date()
    three_days_ago = today - timedelta(days=3)
    seven_days_ago = today - timedelta(days=7)

    # Query parameters
    start_date = request.args.get("start")
    end_date = request.args.get("end")

    if start_date and end_date:
        start = start_date
        end = end_date
    else:
        start = None
        end = None

    # Build query
    query = "SELECT * FROM activities"
    params = ()
    if start and end:
        query += " WHERE date BETWEEN ? AND ? ORDER BY date DESC"
        params = (start, end)
    else:
        query += " ORDER BY date DESC"

    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute(query, params)
    activities_list = cursor.fetchall()
    conn.close()

    # Pass pre-calculated dates to template for buttons
    return render_template(
        "activities.html",
        activities=activities_list,
        today=today.strftime('%Y-%m-%d'),
        three_days_start=three_days_ago.strftime('%Y-%m-%d'),
        seven_days_start=seven_days_ago.strftime('%Y-%m-%d')
    )

@app.route("/delete/<int:activity_id>", methods=["POST"])
def delete_activity(activity_id):
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM activities WHERE id = ?", (activity_id,))
    conn.commit()
    conn.close()
    flash(f"تم حذف النشاط رقم {activity_id}", "success")
    return redirect(url_for("activities"))

@app.route("/edit/<int:activity_id>", methods=["GET", "POST"])
def edit_activity(activity_id):
    conn = get_conn()
    cursor = conn.cursor()
    
    if request.method == "POST":
        # Get form data
        data = {
            "date": request.form.get("date"),
            "group": request.form.get("group"),
            "activity_type": request.form.get("activity_type"),
            "place": request.form.get("place"),
            "time": request.form.get("time"),
            "leaders_count": int(request.form.get("leaders_count", 0)),
            "jawele_count": int(request.form.get("jawele_count", 0)),
            "kashefe_count": int(request.form.get("kashefe_count", 0)),
            "ashbele_count": int(request.form.get("ashbele_count", 0)),
            "bara3em_count": int(request.form.get("bara3em_count", 0)),
            "non_scouts_count": int(request.form.get("non_scouts_count", 0)),
            "occasion": request.form.get("occasion"),
            "paragraphs": request.form.getlist("paragraphs[]"),
            "cost": int(request.form.get("cost", 0))
        }

        # Update DB
        cursor.execute("""
            UPDATE activities
            SET date=?, group_name=?, activity_type=?, place=?, time=?, 
                leaders_count=?, jawele_count=?, kashefe_count=?, ashbele_count=?, bara3em_count=?, 
                non_scouts_count=?, occasion=?, paragraphs=?, cost=?, updated_at=DATETIME('now','localtime')
            WHERE id=?
        """, (
            data["date"], data["group"], data["activity_type"], data["place"], data["time"],
            data["leaders_count"], data["jawele_count"], data["kashefe_count"], data["ashbele_count"], data["bara3em_count"],
            data["non_scouts_count"], data["occasion"], "\n".join(data["paragraphs"]), data["cost"],
            activity_id
        ))
        conn.commit()
        conn.close()
        flash("تم تعديل النشاط بنجاح", "success")
        return redirect(url_for("activities"))

    # GET: fetch existing activity for prefill
    cursor.execute("SELECT * FROM activities WHERE id = ?", (activity_id,))
    activity = cursor.fetchone()
    print(activity)
    conn.close()

    if not activity:
        flash("النشاط غير موجود", "error")
        return redirect(url_for("activities"))

    return render_template("edit_activity.html", activity=activity)

@app.route("/uptime", methods=["GET", "POST"])
def uptime():
    return render_template("uptime.html")

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)





