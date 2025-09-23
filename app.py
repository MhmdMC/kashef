from flask import Flask, render_template, request, redirect, url_for, flash
from datetime import datetime
import pytz
import requests
import os

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev_secret")

# 🔹 Telegram config
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")

def send_telegram_msg(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {"chat_id": CHAT_ID, "text": message, "parse_mode": "HTML"}
    requests.post(url, data=data)

def send_telegram_file(message, photo):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
    data = {"chat_id": CHAT_ID, "caption": message, "parse_mode": "HTML"}
    files = {"photo": photo}
    requests.post(url, data=data, files=files)

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        form_data = {
            "التاريخ": request.form.get("date"),
            "الفرقة": request.form.get("group"),
            "نوع النشاط": request.form.get("activity_type"),
            "المكان": request.form.get("place"),
            "وقت التنفيذ": request.form.get("time"),
            "عدد القادة": request.form.get("leaders"),
            "عدد الكشفيين": request.form.get("scouts"),
            "عدد غير الكشفيين": request.form.get("non_scouts"),
            "مناسبة النشاط": request.form.get("occasion") or "لا يوجد",
            "الفقرات المنفذة": request.form.getlist("paragraphs[]"),
            "التكلفة": request.form.get("cost") or "0",
        }

        # Validation
        if not form_data["الفقرات المنفذة"] or all(not p.strip() for p in form_data["الفقرات المنفذة"]):
            flash("يجب إضافة فقرة واحدة على الأقل.", "error")
            return redirect(url_for("index"))

        # 🔹 Create Telegram message
        msg = f"📌 <b>نموذج النشاط تم الإرسال</b>\n"
        for k, v in form_data.items():
            if k == "الفقرات المنفذة":
                paragraphs = "\n".join([f"- {p}" for p in v if p.strip()])
                msg += f"{k}:\n{paragraphs}\n"
            else:
                msg += f"{k}: {v}\n"

        send_telegram_msg(msg)
        
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

@app.route("/uptime", methods=["GET", "POST"])
def uptime():
    return render_template("uptime.html")

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)





