from flask import Flask, request, render_template, session, redirect, url_for
import requests
import os

app = Flask(__name__)
app.secret_key = "mentorai_secret_key_2024"
API_KEY = "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"

@app.route("/")
def home():
    return render_template("index.html", username="Guest")

@app.route("/get", methods=["POST"])
def get_bot_response():
    user_text = request.data.decode("utf-8")
    try:
        response = requests.post(
            url="https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "meta-llama/llama-3-8b-instruct:free",
                "messages": [
                    {"role": "system", "content": "You are MentorAI, a smart and helpful mentor."},
                    {"role": "user", "content": user_text}
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

if __name__ == "__main__":
    app.run(debug=True)
