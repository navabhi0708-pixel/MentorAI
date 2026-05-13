from flask import Flask, request, render_template, redirect, url_for, session, jsonify
import requests
import mysql.connector
import bcrypt
import random
import os

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "mentorai_secret_key_2024")
app.config['PERMANENT_SESSION_LIFETIME'] = 60 * 60 * 24 * 30

# API Keys from environment variables (NEVER hardcode these!)
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
BREVO_API_KEY = os.environ.get("BREVO_API_KEY")
EMAIL_ADDRESS = "mentorai.otp@gmail.com"

SYSTEM_PROMPT = "You are MentorAI, a smart and helpful mentor. Help users learn, grow, and solve problems clearly and concisely."


def build_messages(history, user_text):
    """Build full conversation history for API calls."""
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for msg in history:
        role = "user" if msg["type"] == "user" else "assistant"
        messages.append({"role": role, "content": msg["text"]})
    messages.append({"role": "user", "content": user_text})
    return messages


def get_ai_response(user_text, history=[]):
    """Try Gemini first, fallback to Groq if it fails."""
    messages = build_messages(history, user_text)

    # ✅ PRIMARY: Gemini Flash
    try:
        if GEMINI_API_KEY:
            # Convert messages to Gemini format
            gemini_contents = []
            for msg in messages[1:]:  # Skip system prompt
                role = "user" if msg["role"] == "user" else "model"
                gemini_contents.append({
                    "role": role,
                    "parts": [{"text": msg["content"]}]
                })

            response = requests.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}",
                headers={"Content-Type": "application/json"},
                json={
                    "system_instruction": {
                        "parts": [{"text": SYSTEM_PROMPT}]
                    },
                    "contents": gemini_contents,
                    "generationConfig": {
                        "temperature": 0.7,
                        "maxOutputTokens": 1024
                    }
                },
                timeout=15
            )
            result = response.json()
            if "candidates" in result:
                return result["candidates"][0]["content"]["parts"][0]["text"]
            else:
                print("Gemini error:", result)
    except Exception as e:
        print("Gemini failed, trying Groq:", e)

    # ✅ FALLBACK: Groq
    try:
        if GROQ_API_KEY:
            response = requests.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {GROQ_API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "llama-3.1-8b-instant",
                    "messages": messages
                },
                timeout=15
            )
            result = response.json()
            if "choices" in result:
                return result["choices"][0]["message"]["content"]
            else:
                print("Groq error:", result)
    except Exception as e:
        print("Groq also failed:", e)

    return "MentorAI is temporarily unavailable. Please try again in a moment!"


def send_otp_email(to_email, otp):
    try:
        url = "https://api.brevo.com/v3/smtp/email"
        headers = {
            "accept": "application/json",
            "api-key": BREVO_API_KEY,
            "content-type": "application/json"
        }
        data = {
            "sender": {"name": "MentorAI", "email": EMAIL_ADDRESS},
            "to": [{"email": to_email}],
            "subject": "MentorAI - Your OTP Verification Code",
            "htmlContent": f"""
            <html><body style="font-family:Arial,sans-serif;background:#0f172a;color:white;padding:30px;">
            <div style="max-width:400px;margin:auto;background:#1e293b;border-radius:16px;padding:30px;text-align:center;">
            <h2 style="color:#60a5fa;">MentorAI</h2>
            <p style="color:#94a3b8;">Your OTP Verification Code</p>
            <div style="font-size:36px;font-weight:bold;letter-spacing:10px;color:white;background:#3b82f6;padding:16px;border-radius:12px;margin:20px 0;">{otp}</div>
            <p style="color:#64748b;font-size:13px;">This code expires in 10 minutes.</p>
            </div></body></html>
            """
        }
        response = requests.post(url, headers=headers, json=data)
        print("Brevo response:", response.status_code, response.text)
        return response.status_code == 201
    except Exception as e:
        print("Email error:", e)
        return False


def get_db():
    return mysql.connector.connect(
        host=os.environ.get("DB_HOST"),
        user=os.environ.get("DB_USER"),
        password=os.environ.get("DB_PASSWORD"),
        database=os.environ.get("DB_NAME"),
        port=int(os.environ.get("DB_PORT", 3306))
    )


def init_db():
    try:
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
    except Exception as e:
        print("DB init error:", e)


@app.route("/")
def home():
    if "user_id" not in session:
        return redirect(url_for("login"))
    return render_template("index.html", username=session.get("username"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if "user_id" in session:
        return redirect(url_for("home"))
    if request.method == "GET":
        return render_template("Login.html")

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
        if not user["is_verified"]:
            return jsonify({"success": False, "message": "Please verify your email first!"})
        if bcrypt.checkpw(password.encode("utf-8"), user["password"].encode("utf-8")):
            session.permanent = True
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            return jsonify({"success": True})
        else:
            return jsonify({"success": False, "message": "Incorrect password!"})
    except Exception as e:
        return jsonify({"success": False, "message": "Error: " + str(e)})


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if "user_id" in session:
        return redirect(url_for("home"))
    if request.method == "GET":
        return render_template("Signup.html")

    data = request.get_json()
    username = data.get("username", "").strip()
    email = data.get("email", "").strip()
    password = data.get("password", "").strip()

    if not username or not email or not password:
        return jsonify({"success": False, "message": "Please fill all fields!"})
    if len(password) < 6:
        return jsonify({"success": False, "message": "Password must be at least 6 characters!"})

    try:
        db = get_db()
        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE username = %s OR email = %s", (username, email))
        existing = cursor.fetchone()
        cursor.close()
        db.close()
        if existing:
            return jsonify({"success": False, "message": "Username or email already exists!"})
    except Exception as e:
        return jsonify({"success": False, "message": "Error: " + str(e)})

    hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    otp = str(random.randint(100000, 999999))
    session["otp"] = otp
    session["otp_email"] = email
    session["otp_username"] = username
    session["otp_password"] = hashed

    if send_otp_email(email, otp):
        return jsonify({"success": True, "message": "OTP sent!"})
    else:
        return jsonify({"success": False, "message": "Could not send OTP! Check email address."})


@app.route("/verify-otp", methods=["GET", "POST"])
def verify_otp():
    if request.method == "GET":
        return render_template("Verify_otp.html")

    data = request.get_json()
    entered_otp = data.get("otp", "").strip()

    if "otp" not in session:
        return jsonify({"success": False, "message": "Session expired! Please signup again."})

    if entered_otp == session["otp"]:
        try:
            db = get_db()
            cursor = db.cursor()
            cursor.execute(
                "INSERT INTO users (username, email, password, is_verified) VALUES (%s, %s, %s, 1)",
                (session["otp_username"], session["otp_email"], session["otp_password"])
            )
            db.commit()
            cursor.close()
            db.close()

            session.pop("otp", None)
            session.pop("otp_email", None)
            session.pop("otp_username", None)
            session.pop("otp_password", None)

            return jsonify({"success": True})
        except mysql.connector.IntegrityError:
            return jsonify({"success": False, "message": "Username or email already exists!"})
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

    data = request.get_json()
    user_text = data.get("message", "")
    history = data.get("history", [])

    response = get_ai_response(user_text, history)
    return response


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
