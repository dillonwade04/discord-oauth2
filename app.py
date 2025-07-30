from flask import Flask, redirect, request
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
                background: url('https://raw.githubusercontent.com/dillonwade04/assets/main/cssobanner.gif') no-repeat center center fixed;
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
                <img class="logo" src="https://raw.githubusercontent.com/dillonwade04/assets/main/CSSO_sheriff_STAR.png" alt="CSSO Logo">
                <h1>Carolina State Sheriff's Office</h1>
                <p>Welcome to the CSSO Portal. Log in with Discord to continue.</p>
                <img class="discord-logo" src="https://raw.githubusercontent.com/dillonwade04/assets/main/discord.png" alt="Discord">
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
    guilds = requests.get("https://discord.com/api/users/@me/guilds", headers=headers).json()

    guild_list = "<br>".join([g['name'] for g in guilds])
    return f"<h2>Servers you are in:</h2><p>{guild_list}</p>"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
