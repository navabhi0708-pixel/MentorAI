from flask import Flask, request, render_template
import requests

app = Flask(__name__)

API_KEY = "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"

@app.route("/")
def home():
    return render_template("index.html", username="Guest")

@app.route("/get", methods=["POST"])
def get_bot_response():
    user_text = request.data.decode("utf-8")
    try:
        response = requests.post(
            url="https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "llama3-8b-8192",
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
