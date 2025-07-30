from flask import Flask, redirect, request, jsonify
import requests
import os

app = Flask(__name__)

CLIENT_ID = os.environ.get("DISCORD_CLIENT_ID", "YOUR_CLIENT_ID")
CLIENT_SECRET = os.environ.get("DISCORD_CLIENT_SECRET", "YOUR_CLIENT_SECRET")
REDIRECT_URI = os.environ.get("DISCORD_REDIRECT_URI", "http://localhost:5000/callback")

@app.route("/")
def home():
    return """
    <html>
    <head>
        <title>Carolina State Sheriff's Office</title>
        <style>
            body {
                background: #121212;
                color: white;
                font-family: Arial, sans-serif;
                text-align: center;
                margin: 0;
                padding: 0;
            }
            .container {
                display: flex;
                flex-direction: column;
                align-items: center;
                justify-content: center;
                height: 100vh;
            }
            img {
                width: 150px;
                margin-bottom: 20px;
            }
            .login-btn {
                background-color: #5865F2;
                color: white;
                padding: 12px 25px;
                border-radius: 8px;
                font-size: 16px;
                text-decoration: none;
                font-weight: bold;
                transition: background 0.2s;
            }
            .login-btn:hover {
                background-color: #4752C4;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <img src="https://raw.githubusercontent.com/dillonwade04/assets/main/CSSO_sheriff_STAR.png" alt="CSSO Logo">
            <h1>Carolina State Sheriff's Office</h1>
            <p>Welcome to the CSSO Portal. Please log in with Discord to continue.</p>
            <a class="login-btn" href="/login">Login with Discord</a>
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
    guilds = requests.get("https://discord.com/api/users/@me/guilds", headers=headers).json()

    # Show guilds in a clean format
    guild_list = "<br>".join([g['name'] for g in guilds])
    return f"<h2>Servers you are in:</h2><p>{guild_list}</p>"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
