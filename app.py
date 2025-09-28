from importlib.resources import files
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from datetime import datetime, timedelta
import pytz
import requests
import os
import sqlite3

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev_secret")

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")
DB_PATH = "app.db"

def get_conn():
    return sqlite3.connect(DB_PATH)

def get_today():
    ttz = pytz.timezone("Asia/Beirut")
    return datetime.now(ttz).date()

def insert_activity(data):
    conn = None
    try:
        conn = get_conn()
        cursor = conn.cursor()
        created_at = datetime.now(pytz.timezone("Asia/Beirut")).strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute("""
            INSERT INTO activities (
                date, group_name, activity_type, time, occasion, place,
                leaders_count, jawele_count, kashefe_count, ashbele_count,
                bara3em_count, non_scouts_count, paragraphs, cost, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            data["cost"],
            created_at
        ))
        conn.commit()
        return cursor.lastrowid
    except Exception as e:
        print("DB Insert Error:", e, data)
        return None
    finally:
        if conn:
            conn.close()

# Function to update an existing activity TODO
def update_activity(activity_id, data):
    ...

def send_telegram_files(message, files):    
    doc_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendDocument"
    for f in files:
        response = requests.post(
            doc_url,
            data={
                "chat_id": CHAT_ID,
                "caption": f"ID: {message}"
            },
            files={"document": (f.filename, f.stream)}
        )
        if response.status_code != 200:
            print(f"Failed to send {f.filename}: {response.text}")

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

        id = insert_activity(form_data)

        files = request.files.getlist("files[]")
        send_telegram_files(id, files)

        return redirect(url_for("index"))

    return render_template("index.html", today=get_today())

@app.route("/activities", methods=["GET", "POST"])
def activities():
    # Use Beirut local date defaults
    today = get_today()
    three_days_ago = today - timedelta(days=3)
    seven_days_ago = today - timedelta(days=7)

    # Read filters from request.values so POST and GET both work
    start = request.values.get("start", "").strip() or None
    end = request.values.get("end", "").strip() or None
    group = request.values.get("group", "").strip() or None
    q = request.values.get("q", "").strip() or None

    admin = request.values.get("admin", "").strip() or None
    admin_filter = request.values.get("adminFilter", "").strip() or None


    # Build SQL with conditional WHERE clauses
    query = "SELECT * FROM activities"
    conditions = []
    params = []

    if start and end:
        conditions.append("date BETWEEN ? AND ?")
        params.extend([start, end])

    if group and group != "كل الفرق":
        conditions.append("group_name = ?")
        params.append(group)

    if q:
        # treat q as subtext (case-insensitive) across several text columns, or exact id match
        try:
            q_id = int(q)
        except Exception:
            q_id = -1
        q_like = f"%{q.lower()}%"
        conditions.append("(id = ? OR lower(group_name) LIKE ? OR lower(activity_type) LIKE ? OR lower(place) LIKE ? OR lower(occasion) LIKE ? OR lower(paragraphs) LIKE ?)")
        params.extend([q_id, q_like, q_like, q_like, q_like, q_like])

    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    if admin_filter and admin_filter != "الكل":
        if admin_filter == "غير مضاف":
            query += " AND checked = 0"
        elif admin_filter == "مضاف":
            query += " AND checked = 1"
        elif admin_filter == "معدل بعد الإضافة":
            query += " AND checked = -1"
    # Sort by created_at descending
    query += " ORDER BY created_at DESC"

    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute(query, tuple(params))
    activities_list = cursor.fetchall()
    conn.close()

    # Pass current filter values back to template so inputs keep their values
    return render_template(
        "activities.html",
        activities=activities_list,
        today=today.strftime("%Y-%m-%d"),
        three_days_start=three_days_ago.strftime("%Y-%m-%d"),
        seven_days_start=seven_days_ago.strftime("%Y-%m-%d"),
        current_start=start or "",
        current_end=end or "",
        current_group=group or "",
        current_q=q or "",
        admin=admin,
        admin_filter=admin_filter or ""
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
        updated_at = datetime.now(pytz.timezone("Asia/Beirut")).strftime("%Y-%m-%d %H:%M:%S")

        cursor.execute("""
            UPDATE activities
            SET date=?, group_name=?, activity_type=?, place=?, time=?, 
                leaders_count=?, jawele_count=?, kashefe_count=?, ashbele_count=?, bara3em_count=?, 
                non_scouts_count=?, occasion=?, paragraphs=?, cost=?, updated_at=?
            WHERE id=?
        """, (
            data["date"], data["group"], data["activity_type"], data["place"], data["time"],
            data["leaders_count"], data["jawele_count"], data["kashefe_count"], data["ashbele_count"], data["bara3em_count"],
            data["non_scouts_count"], data["occasion"], "\n".join(data["paragraphs"]), data["cost"],
            updated_at,
            activity_id
        ))
        conn.commit()
        conn.close()
        flash("تم تعديل النشاط بنجاح", "success")
        return redirect(url_for("activities"))

    # GET: fetch existing activity for prefill
    cursor.execute("SELECT * FROM activities WHERE id = ?", (activity_id,))
    activity = cursor.fetchone()

    if not activity:
        conn.close()
        flash("النشاط غير موجود", "error")
        return redirect(url_for("activities"))

    # mark as being edited (-1)
    if activity[17] == 1:  # checked column
        checked_at = datetime.now(pytz.timezone("Asia/Beirut")).strftime("%Y-%m-%d %H:%M:%S")
        try:
            cursor.execute("UPDATE activities SET checked = ?, checked_at = ? WHERE id = ?", (-1, checked_at, activity_id))
            conn.commit()
            # re-fetch to include new checked state
            cursor.execute("SELECT * FROM activities WHERE id = ?", (activity_id,))
            activity = cursor.fetchone()
        except Exception as e:
            print("Failed to mark activity as editing:", e)
        finally:
            conn.close()

    return render_template("edit_activity.html", activity=activity)


@app.route('/toggle_checked/<int:activity_id>', methods=['POST'])
def toggle_checked(activity_id):
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT checked FROM activities WHERE id = ?", (activity_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return jsonify({"success": False, "error": "not_found"}), 404

    current = row[0] if row[0] is not None else 0
    new = 1 if current != 1 else 0
    if new == 1:
        checked_at = datetime.now(pytz.timezone("Asia/Beirut")).strftime("%Y-%m-%d %H:%M:%S")
    else:
        checked_at = None
    try:
        cursor.execute("UPDATE activities SET checked = ?, checked_at = ? WHERE id = ?", (new, checked_at, activity_id))
        conn.commit()
    except Exception as e:
        conn.close()
        print("Failed toggling checked:", e, activity_id)
        return jsonify({"success": False, "error": "db_error"}), 500

    conn.close()
    return jsonify({"success": True, "checked": new})

@app.route("/uptime", methods=["GET", "POST"])
def uptime():
    return render_template("uptime.html")

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)





