"""Small Flask server: the browser sends what was heard, we reply as the coach."""
import os

from dotenv import find_dotenv, load_dotenv
from flask import Flask, jsonify, request

from coach import Session
from parser import parse

# Put GROQ_API_KEY and GROQ_MODEL from .env into os.environ.
env_path = find_dotenv(usecwd=True)
load_dotenv(env_path)
# Startup check. Never print the key itself, only whether it was found.
print(f".env file: {env_path or 'not found'}")
print(f"GROQ_API_KEY found: {'yes' if os.getenv('GROQ_API_KEY') else 'no'}")
print(f"Groq model: {os.getenv('GROQ_MODEL') or 'not set'}")

app = Flask(__name__)
session = Session()  # one workout at a time, kept in memory


@app.get("/")
def index():
    return app.send_static_file("index.html")


@app.post("/api/turn")
def turn():
    text = (request.get_json(silent=True) or {}).get("text", "")
    heard = parse(text)
    reply = session.handle(heard["intent"], heard["weight"], heard["reps"])
    return jsonify(
        heard=heard,
        reply=reply,
        current=session.describe_current(),
        log=session.log,
    )


@app.post("/api/reset")
def reset():
    global session
    session = Session()
    return jsonify(current=session.describe_current(), log=session.log)


if __name__ == "__main__":
    app.run(debug=True)
