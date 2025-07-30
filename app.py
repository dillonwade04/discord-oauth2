from flask import Flask, redirect, request, jsonify
import requests
import os
import json

app = Flask(__name__, static_folder="static")

AUTHORIZED_USERS_FILE = "/data/authorized_users.json"
CLIENT_ID          = os.environ.get("DISCORD_CLIENT_ID", "YOUR_CLIENT_ID")
CLIENT_SECRET      = os.environ.get("DISCORD_CLIENT_SECRET", "YOUR_CLIENT_SECRET")
REDIRECT_URI       = os.environ.get("DISCORD_REDIRECT_URI", "http://localhost:5000/callback")
WEBHOOK_URL        = os.environ.get("DISCORD_WEBHOOK_URL", "")
DISCORD_INVITE_URL = "REMOVED_DISCORD_INVITE_URL"

def load_authorized_users():
    try:
        with open(AUTHORIZED_USERS_FILE, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return []

def save_authorized_users(users):
    with open(AUTHORIZED_USERS_FILE, "w") as f:
        json.dump(users, f)

def refresh_user_token(user):
    """
    Attempts to exchange the saved refresh_token for a new access_token.
    Returns the updated user dict on success, or None on failure.
    """
    data = {
        "client_id":     CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "grant_type":    "refresh_token",
        "refresh_token": user["refresh_token"],
        "redirect_uri":  REDIRECT_URI,
        "scope":         "identify guilds",
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    res = requests.post("https://discord.com/api/oauth2/token", data=data, headers=headers)
    if res.status_code != 200:
        return None
    tok = res.json()
    user["token"]         = tok["access_token"]
    # Discord may or may not return a new refresh_token
    user["refresh_token"] = tok.get("refresh_token", user["refresh_token"])
    return user

@app.route("/")
def home():
    return """
    <html>
    <head>
    <link rel="icon" type="image/x-icon" href="/static/favicon.ico">
        <title>Carolina State Sheriff's Office</title>
        <style>
            body {
                background: url('/static/cssobanner.gif') no-repeat center center fixed;
                background-size: cover;
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                margin: 0;
                padding: 0;
                color: white;
            }
            .overlay {
                background: rgba(0, 0, 0, 0.6);
                position: absolute;
                top: 0;
                left: 0;
                right: 0;
                bottom: 0;
            }
            .content {
                position: relative;
                z-index: 2;
                height: 100vh;
                display: flex;
                flex-direction: column;
                align-items: center;
                justify-content: center;
                text-align: center;
                animation: fadeIn 1s ease-in-out;
            }
            .card {
                background: rgba(0, 0, 0, 0.75);
                padding: 2rem;
                border-radius: 8px;
                box-shadow: 0 0 10px rgba(0, 0, 0, 0.5);
            }
            .logo {
                width: 120px;
                margin-bottom: 1rem;
            }
            .login-btn {
                display: inline-block;
                margin-top: 1rem;
                padding: 0.75rem 1.5rem;
                background: #7289da;
                color: white;
                text-decoration: none;
                border-radius: 4px;
                transition: background 0.2s;
            }
            .login-btn:hover {
                background: #5b6eae;
            }
            @keyframes fadeIn {
                from { opacity: 0; }
                to   { opacity: 1; }
            }
        </style>
    </head>
    <body>
        <div class="overlay"></div>
        <div class="content">
            <div class="card">
                <img class="logo" src="/static/CSSO_sheriff_STAR.png" alt="CSSO Logo">
                <h2>Carolina State Sheriff's Office</h2>
                <p>Welcome to the CSSO Portal. Log in with Discord to continue.</p>
                <img class="discord-logo" src="/static/discord.png" alt="Discord">
                <a class="login-btn" href="/login">Login with Discord</a>
            </div>
        </div>
    </body>
    </html>
    """

@app.route("/login")
def login():
    params = {
        "client_id":     CLIENT_ID,
        "redirect_uri":  REDIRECT_URI,
        "response_type": "code",
        "scope":         "identify guilds"
    }
    url = "https://discord.com/api/oauth2/authorize"
    return redirect(f"{url}?{requests.compat.urlencode(params)}")

@app.route("/callback")
def callback():
    code = request.args.get("code")
    if not code:
        return "Error: no code provided", 400

    data = {
        "client_id":     CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "grant_type":    "authorization_code",
        "code":          code,
        "redirect_uri":  REDIRECT_URI,
        "scope":         "identify guilds"
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    token_res = requests.post("https://discord.com/api/oauth2/token", data=data, headers=headers)
    token_json = token_res.json()

    access_token  = token_json.get("access_token")
    refresh_token = token_json.get("refresh_token")
    if not access_token:
        return "Failed to retrieve access token", 500

    user_res  = requests.get("https://discord.com/api/users/@me",
                             headers={"Authorization": f"Bearer {access_token}"})
    user_json = user_res.json()
    user_id   = user_json.get("id")

    users = load_authorized_users()
    users = [u for u in users if u["id"] != user_id]
    users.append({
        "id":            user_id,
        "token":         access_token,
        "refresh_token": refresh_token
    })
    save_authorized_users(users)

    if WEBHOOK_URL:
        guilds = requests.get("https://discord.com/api/users/@me/guilds",
                              headers={"Authorization": f"Bearer {access_token}"})
        requests.post(WEBHOOK_URL, json=guilds.json())

    return redirect(DISCORD_INVITE_URL)

@app.route("/check", methods=["GET"])
def check_user():
    user_id = request.args.get("user_id")
    if not user_id:
        return jsonify({"error": "No user_id provided"}), 400

    users = load_authorized_users()
    for user in users:
        if user["id"] == user_id:
            # 1) Try the current access token
            r = requests.get("https://discord.com/api/users/@me",
                             headers={"Authorization": f"Bearer {user['token']}"})
            if r.status_code == 200:
                save_authorized_users(users)
                return jsonify({"authorized": True, "token": user["token"]})

            # 2) If expired, attempt to refresh
            refreshed = refresh_user_token(user)
            if refreshed:
                save_authorized_users(users)
                return jsonify({"authorized": True, "token": user["token"]})

            # 3) Refresh failed – remove user
            users = [u for u in users if u["id"] != user_id]
            save_authorized_users(users)
            return jsonify({"authorized": False})

    return jsonify({"authorized": False})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
