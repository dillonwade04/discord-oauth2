from flask import Flask, redirect, request, jsonify, send_from_directory
import requests
import os
import json

app = Flask(__name__, static_folder="static")

AUTHORIZED_USERS_FILE = "authorized_users.json"
CLIENT_ID = os.environ.get("DISCORD_CLIENT_ID", "YOUR_CLIENT_ID")
CLIENT_SECRET = os.environ.get("DISCORD_CLIENT_SECRET", "YOUR_CLIENT_SECRET")
REDIRECT_URI = os.environ.get("DISCORD_REDIRECT_URI", "http://localhost:5000/callback")
WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL", "YOUR_WEBHOOK_URL")

def load_authorized_users():
    try:
        with open(AUTHORIZED_USERS_FILE, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return []

def save_authorized_users(users):
    with open(AUTHORIZED_USERS_FILE, "w") as f:
        json.dump(users, f)

@app.route("/authorize", methods=["POST"])
def authorize():
    data = request.json
    user_id = data.get("user_id")
    if not user_id:
        return jsonify({"error": "No user_id provided"}), 400

    users = load_authorized_users()
    if user_id not in users:
        users.append(user_id)
        save_authorized_users(users)

    return jsonify({"status": "ok", "user_id": user_id})

@app.route("/check", methods=["GET"])
def check_user():
    user_id = request.args.get("user_id")
    if not user_id:
        return jsonify({"error": "No user_id provided"}), 400

    users = load_authorized_users()
    return jsonify({"authorized": user_id in users})

@app.route("/")
def home():
    return """
    <html>
    <head><title>Carolina State Sheriff's Office</title></head>
    <body>
    <h2>Carolina State Sheriff's Office Portal</h2>
    <a href='/login'>Login with Discord</a>
    </body>
    </html>
    """

@app.route("/login")
def login():
    return redirect(f"https://discord.com/api/oauth2/authorize?client_id={CLIENT_ID}&redirect_uri={REDIRECT_URI}&response_type=code&scope=identify%20guilds")

@app.route("/callback")
def callback():
    code = request.args.get("code")
    if not code:
        return "No code provided", 400

    data = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT_URI,
        "scope": "identify guilds"
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    r = requests.post("https://discord.com/api/oauth2/token", data=data, headers=headers)
    r.raise_for_status()
    credentials = r.json()

    access_token = credentials.get("access_token")
    headers = {"Authorization": f"Bearer {access_token}"}
    user = requests.get("https://discord.com/api/users/@me", headers=headers).json()

    # Store user_id
    user_id = str(user.get("id"))
    users = load_authorized_users()
    if user_id not in users:
        users.append(user_id)
        save_authorized_users(users)

    return f"<h1>Login Successful!</h1><p>You can now close this page.</p>"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
