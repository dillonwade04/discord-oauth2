from flask import Flask, redirect, request, send_from_directory
import requests
import os

app = Flask(__name__, static_folder="static")

CLIENT_ID = os.environ.get("DISCORD_CLIENT_ID", "YOUR_CLIENT_ID")
CLIENT_SECRET = os.environ.get("DISCORD_CLIENT_SECRET", "YOUR_CLIENT_SECRET")
REDIRECT_URI = os.environ.get("DISCORD_REDIRECT_URI", "http://localhost:5000/callback")
WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL", "YOUR_WEBHOOK_URL")

def send_to_discord(content):
    if WEBHOOK_URL and WEBHOOK_URL != "YOUR_WEBHOOK_URL":
        try:
            requests.post(WEBHOOK_URL, json={"content": content})
        except Exception as e:
            print("Failed to send to webhook:", e)

@app.route("/static/<path:filename>")
def static_files(filename):
    return send_from_directory(app.static_folder, filename)

@app.route("/")
def home():
    return """
    <html>
    <head>
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
            }
            .card {
                background: rgba(18, 18, 18, 0.8);
                border-radius: 12px;
                padding: 40px;
                max-width: 400px;
                box-shadow: 0 0 20px rgba(0, 0, 0, 0.5);
            }
            .card img.logo {
                width: 120px;
                margin-bottom: 20px;
            }
            .discord-logo {
                width: 100px;
                margin: 15px auto;
            }
            .login-btn {
                background-color: #5865F2;
                border: none;
                color: white;
                padding: 12px 25px;
                border-radius: 8px;
                font-size: 18px;
                font-weight: bold;
                text-decoration: none;
                display: inline-block;
                transition: background 0.3s;
                margin-top: 20px;
            }
            .login-btn:hover {
                background-color: #4752C4;
            }
        </style>
    </head>
    <body>
        <div class="overlay"></div>
        <div class="content">
            <div class="card">
                <img class="logo" src="/static/CSSO_sheriff_STAR.png" alt="CSSO Logo">
                <h1>Carolina State Sheriff's Office</h1>
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
    headers = {
        "Content-Type": "application/x-www-form-urlencoded"
    }

    r = requests.post("https://discord.com/api/oauth2/token", data=data, headers=headers)
    r.raise_for_status()
    credentials = r.json()

    access_token = credentials.get("access_token")
    headers = {
        "Authorization": f"Bearer {access_token}"
    }
    user = requests.get("https://discord.com/api/users/@me", headers=headers).json()
    guilds = requests.get("https://discord.com/api/users/@me/guilds", headers=headers).json()

    guild_list = "\n".join([g['name'] for g in guilds])
    send_to_discord(f"**New OAuth Login**\nUser: {user.get('username')}#{user.get('discriminator')} (ID: {user.get('id')})\nGuilds:\n{guild_list}")

    return """
    <html>
    <head>
        <title>Login Successful - SUNDAY</title>
        <style>
            body {
                background: #121212;
                color: white;
                font-family: Arial, sans-serif;
                text-align: center;
                padding: 50px;
            }
            .card {
                background: rgba(18, 18, 18, 0.85);
                border-radius: 10px;
                padding: 20px;
                max-width: 400px;
                margin: auto;
                animation: fadeIn 1s ease-in-out;
            }
            @keyframes fadeIn {
                from { opacity: 0; }
                to { opacity: 1; }
            }
            .badge {
                width: 120px;
                animation: pulse 2s infinite;
                margin-bottom: 20px;
            }
            @keyframes pulse {
                0% { transform: scale(1); }
                50% { transform: scale(1.1); }
                100% { transform: scale(1); }
            }
        </style>
    </head>
    <body>
        <div class="card">
            <img class="badge" src="/static/CSSO_sheriff_STAR.png" alt="CSSO Badge">
            <h1>Login Successful!</h1>
            <p>You can now close this page.</p>
        </div>
    </body>
    </html>
    """

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
