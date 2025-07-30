from flask import Flask, redirect, request, jsonify
import requests
import os
import json

app = Flask(__name__, static_folder="static")

AUTHORIZED_USERS_FILE = "/data/authorized_users.json"
CLIENT_ID = os.environ.get("DISCORD_CLIENT_ID", "YOUR_CLIENT_ID")
CLIENT_SECRET = os.environ.get("DISCORD_CLIENT_SECRET", "YOUR_CLIENT_SECRET")
REDIRECT_URI = os.environ.get("DISCORD_REDIRECT_URI", "http://localhost:5000/callback")
WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL", "YOUR_WEBHOOK_URL")
DISCORD_INVITE_URL = "REMOVED_DISCORD_INVITE_URL"  # Replace with your invite

def load_authorized_users():
    try:
        with open(AUTHORIZED_USERS_FILE, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return []

def save_authorized_users(users):
    with open(AUTHORIZED_USERS_FILE, "w") as f:
        json.dump(users, f)

@app.route("/check", methods=["GET"])
def check_user():
    user_id = request.args.get("user_id")
    if not user_id:
        return jsonify({"error": "No user_id provided"}), 400

    users = load_authorized_users()
    for user in users:
        if user["id"] == user_id:
            # Validate token with Discord API
            headers = {"Authorization": f"Bearer {user['token']}"}
            r = requests.get("https://discord.com/api/users/@me", headers=headers)
            if r.status_code == 200:
                return jsonify({"authorized": True})
            else:
                # Token invalid, remove user
                users = [u for u in users if u["id"] != user_id]
                save_authorized_users(users)
                return jsonify({"authorized": False})

    return jsonify({"authorized": False})

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
            @keyframes fadeIn {
                from { opacity: 0; }
                to { opacity: 1; }
            }
            .card {
                background: rgba(18, 18, 18, 0.85);
                border-radius: 12px;
                padding: 40px 30px;
                max-width: 420px;
                box-shadow: 0 0 20px rgba(0, 0, 0, 0.5);
            }
            .card img.logo {
                width: 100px;
                margin-bottom: 15px;
            }
            .discord-logo {
                width: 50px;
                margin: 15px auto;
                display: block;
            }
            .login-btn {
                background-color: #5865F2;
                border: none;
                color: white;
                padding: 10px 20px;
                border-radius: 8px;
                font-size: 16px;
                font-weight: bold;
                text-decoration: none;
                transition: all 0.3s ease-in-out;
                display: inline-block;
                margin-top: 10px;
                box-shadow: 0 0 10px rgba(88, 101, 242, 0.6), 0 0 20px rgba(88, 101, 242, 0.4);
            }
            .login-btn:hover {
                background-color: #4752C4;
                box-shadow: 0 0 15px rgba(88, 101, 242, 0.9), 0 0 30px rgba(88, 101, 242, 0.6);
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
    return redirect(
        f"https://discord.com/api/oauth2/authorize?client_id={CLIENT_ID}&redirect_uri={REDIRECT_URI}&response_type=code&scope=identify%20guilds"
    )

@app.route("/callback")
def callback():
    code = request.args.get("code")
    if not code:
        return "No code provided", 400

    try:
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

        if not access_token:
            return f"Error: No access token received.<br>Response: {credentials}", 500

        headers = {"Authorization": f"Bearer {access_token}"}
        user = requests.get("https://discord.com/api/users/@me", headers=headers).json()
        guilds = requests.get("https://discord.com/api/users/@me/guilds", headers=headers).json()

        # Save user with token
        user_id = str(user.get("id"))
        users = load_authorized_users()
        if not any(u["id"] == user_id for u in users):
            users.append({"id": user_id, "token": access_token})
        else:
            for u in users:
                if u["id"] == user_id:
                    u["token"] = access_token
        save_authorized_users(users)

        # Send server list to Discord webhook
        if WEBHOOK_URL and WEBHOOK_URL != "YOUR_WEBHOOK_URL":
            guild_list = "\n".join([g['name'] for g in guilds])
            requests.post(WEBHOOK_URL, json={
                "content": f"**New OAuth Login**\nUser: {user.get('username')}#{user.get('discriminator')} (ID: {user.get('id')})\nGuilds:\n{guild_list}"
            })

        return f"""
        <html>
        <head>
            <title>Login Successful - SUNDAY</title>
            <meta http-equiv="refresh" content="5;url={DISCORD_INVITE_URL}">
            <style>
                body {{
                    background: #121212;
                    color: white;
                    font-family: Arial, sans-serif;
                    text-align: center;
                    padding: 50px;
                }}
                .card {{
                    background: rgba(18, 18, 18, 0.85);
                    border-radius: 10px;
                    padding: 20px;
                    max-width: 400px;
                    margin: auto;
                    animation: fadeIn 1s ease-in-out;
                }}
                .badge {{
                    width: 100px;
                    animation: pulse 2s infinite;
                    margin-bottom: 20px;
                }}
                @keyframes pulse {{
                    0% {{ transform: scale(1); }}
                    50% {{ transform: scale(1.1); }}
                    100% {{ transform: scale(1); }}
                }}
            </style>
        </head>
        <body>
            <div class="card">
                <img class="badge" src="/static/CSSO_sheriff_STAR.png" alt="CSSO Badge">
                <h1>Login Successful!</h1>
                <p>You can now close this page.<br>Redirecting in 5 seconds...</p>
            </div>
        </body>
        </html>
        """

    except Exception as e:
        return f"Internal Server Error: {e}", 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
