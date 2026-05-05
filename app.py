from flask import Flask, request, render_template, redirect, url_for, session, jsonify
import requests
import mysql.connector
import bcrypt
import random
import smtplib
import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

app = Flask(__name__)
app.secret_key = "mentorai_secret_key_2024"

API_KEY = "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"  # Apni OpenRouter API key yahan daalo

# ==================== EMAIL CONFIG ====================
EMAIL_ADDRESS = "mentorai.otp@gmail.com"
EMAIL_PASSWORD = "joiz xjqq wfwj lvux"

def send_otp_email(to_email, otp):
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = "MentorAI - Your OTP Verification Code"
        msg["From"] = EMAIL_ADDRESS
        msg["To"] = to_email

        html = f"""
        <html>
        <body style="font-family: Arial, sans-serif; background: #0f172a; color: white; padding: 30px;">
            <div style="max-width: 400px; margin: auto; background: #1e293b; border-radius: 16px; padding: 30px; text-align: center;">
                <h2 style="color: #60a5fa;">MentorAI</h2>
                <p style="color: #94a3b8;">Your OTP Verification Code</p>
                <div style="font-size: 36px; font-weight: bold; letter-spacing: 10px; color: white; background: #3b82f6; padding: 16px; border-radius: 12px; margin: 20px 0;">
                    {otp}
                </div>
                <p style="color: #64748b; font-size: 13px;">This code expires in 10 minutes. Do not share it with anyone.</p>
            </div>
        </body>
        </html>
        """
        msg.attach(MIMEText(html, "html"))

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            server.sendmail(EMAIL_ADDRESS, to_email, msg.as_string())
        return True
    except Exception as e:
        print("Email error:", e)
        return False

# ==================== DATABASE ====================
def get_db():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="123456",
        database="mentorai"
    )

def init_db():
    db = get_db()
    cursor = db.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INT AUTO_INCREMENT PRIMARY KEY,
            username VARCHAR(50) UNIQUE NOT NULL,
            email VARCHAR(100) UNIQUE NOT NULL,
            password VARCHAR(255) NOT NULL,
            is_verified TINYINT(1) DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    db.commit()
    cursor.close()
    db.close()

# ==================== ROUTES ====================

@app.route("/")
def home():
    if "user_id" not in session:
        return redirect(url_for("login"))
    return render_template("index.html", username=session.get("username"))

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template("login.html")

    data = request.get_json()
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()
    remember_me = data.get("remember_me", False)

    if not username or not password:
        return jsonify({"success": False, "message": "Please fill all fields!"})

    try:
        db = get_db()
        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
        user = cursor.fetchone()
        cursor.close()
        db.close()

        if not user:
            return jsonify({"success": False, "message": "User not found!"})

        if not user["is_verified"]:
            return jsonify({"success": False, "message": "Please verify your email first!"})

        if bcrypt.checkpw(password.encode("utf-8"), user["password"].encode("utf-8")):
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            return jsonify({"success": True})
        else:
            return jsonify({"success": False, "message": "Incorrect password!"})
    except Exception as e:
        return jsonify({"success": False, "message": "Error: " + str(e)})

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "GET":
        return render_template("signup.html")

    data = request.get_json()
    username = data.get("username", "").strip()
    email = data.get("email", "").strip()
    password = data.get("password", "").strip()

    if not username or not email or not password:
        return jsonify({"success": False, "message": "Please fill all fields!"})

    if len(password) < 6:
        return jsonify({"success": False, "message": "Password must be at least 6 characters!"})

    hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

    try:
        db = get_db()
        cursor = db.cursor()
        cursor.execute("INSERT INTO users (username, email, password, is_verified) VALUES (%s, %s, %s, 0)",
                       (username, email, hashed))
        db.commit()
        cursor.close()
        db.close()

        # Generate OTP and send email
        otp = str(random.randint(100000, 999999))
        session["otp"] = otp
        session["otp_email"] = email
        session["otp_username"] = username

        if send_otp_email(email, otp):
            return jsonify({"success": True, "message": "OTP sent!"})
        else:
            return jsonify({"success": False, "message": "Could not send OTP. Check email address!"})

    except mysql.connector.IntegrityError:
        return jsonify({"success": False, "message": "Username or email already exists!"})
    except Exception as e:
        return jsonify({"success": False, "message": "Error: " + str(e)})

@app.route("/verify-otp", methods=["GET", "POST"])
def verify_otp():
    if request.method == "GET":
        return render_template("verify_otp.html")

    data = request.get_json()
    entered_otp = data.get("otp", "").strip()

    if "otp" not in session:
        return jsonify({"success": False, "message": "Session expired! Please signup again."})

    if entered_otp == session["otp"]:
        try:
            db = get_db()
            cursor = db.cursor()
            cursor.execute("UPDATE users SET is_verified = 1 WHERE email = %s", (session["otp_email"],))
            db.commit()
            cursor.close()
            db.close()

            session.pop("otp", None)
            session.pop("otp_email", None)
            session.pop("otp_username", None)

            return jsonify({"success": True})
        except Exception as e:
            return jsonify({"success": False, "message": "Error: " + str(e)})
    else:
        return jsonify({"success": False, "message": "Incorrect OTP! Please try again."})

@app.route("/resend-otp", methods=["POST"])
def resend_otp():
    if "otp_email" not in session:
        return jsonify({"success": False, "message": "Session expired!"})

    otp = str(random.randint(100000, 999999))
    session["otp"] = otp

    if send_otp_email(session["otp_email"], otp):
        return jsonify({"success": True})
    else:
        return jsonify({"success": False, "message": "Could not resend OTP!"})

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/get", methods=["POST"])
def get_bot_response():
    if "user_id" not in session:
        return "Please login first!", 401

    user_text = request.data.decode("utf-8")
    try:
        response = requests.post(
            url="https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "meta-llama/llama-3-8b-instruct",
                "messages": [
                    {
                        "role": "system",
                        "content": "You are MentorAI, a smart and helpful mentor. Help users learn, grow, and solve problems clearly and concisely."
                    },
                    {
                        "role": "user",
                        "content": user_text
                    }
                ]
            }
        )
        result = response.json()
        if "choices" in result:
            return result['choices'][0]['message']['content']
        else:
            return "Error: " + str(result)
    except Exception as e:
        return "Error: " + str(e)

# ==================== MAIN ====================
if __name__ == "__main__":
    init_db()
    app.run(debug=True)

# ==================== ROUTES ====================

@app.route("/")
def home():
    if "user_id" not in session:
        return redirect(url_for("login"))
    return render_template("index.html", username=session.get("username"))

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template("login.html")

    data = request.get_json()
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()

    if not username or not password:
        return jsonify({"success": False, "message": "Please fill all fields!"})

    try:
        db = get_db()
        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
        user = cursor.fetchone()
        cursor.close()
        db.close()

        if not user:
            return jsonify({"success": False, "message": "User not found!"})

        if bcrypt.checkpw(password.encode("utf-8"), user["password"].encode("utf-8")):
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            return jsonify({"success": True})
        else:
            return jsonify({"success": False, "message": "Incorrect password!"})
    except Exception as e:
        return jsonify({"success": False, "message": "Error: " + str(e)})

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "GET":
        return render_template("signup.html")

    data = request.get_json()
    username = data.get("username", "").strip()
    email = data.get("email", "").strip()
    password = data.get("password", "").strip()

    if not username or not email or not password:
        return jsonify({"success": False, "message": "Please fill all fields!"})

    if len(password) < 6:
        return jsonify({"success": False, "message": "Password must be at least 6 characters!"})

    hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

    try:
        db = get_db()
        cursor = db.cursor()
        cursor.execute("INSERT INTO users (username, email, password) VALUES (%s, %s, %s)",
                       (username, email, hashed))
        db.commit()
        cursor.close()
        db.close()
        return jsonify({"success": True})
    except mysql.connector.IntegrityError:
        return jsonify({"success": False, "message": "Username or email already exists!"})
    except Exception as e:
        return jsonify({"success": False, "message": "Error: " + str(e)})

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/get", methods=["POST"])
def get_bot_response():
    if "user_id" not in session:
        return "Pehle login karo!", 401

    user_text = request.data.decode("utf-8")
    try:
        response = requests.post(
            url="https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "meta-llama/llama-3-8b-instruct",
                "messages": [
                    {
                        "role": "system",
                        "content": "You are MentorAI, a smart and helpful mentor. Help users learn, grow, and solve problems clearly and concisely."
                    },
                    {
                        "role": "user",
                        "content": user_text
                    }
                ]
            }
        )
        result = response.json()
        if "choices" in result:
            return result['choices'][0]['message']['content']
        else:
            return "Error: " + str(result)
    except Exception as e:
        return "Error: " + str(e)

# ==================== MAIN ====================
if __name__ == "__main__":
    init_db()
    app.run(debug=True)