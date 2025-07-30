from flask import Flask, redirect, request, jsonify
import requests
import os

app = Flask(__name__)

CLIENT_ID = os.environ.get("DISCORD_CLIENT_ID", "YOUR_CLIENT_ID")
CLIENT_SECRET = os.environ.get("DISCORD_CLIENT_SECRET", "YOUR_CLIENT_SECRET")
REDIRECT_URI = os.environ.get("DISCORD_REDIRECT_URI", "http://localhost:5000/callback")

@app.route("/")
def home():
    return f"<a href='/login'>Login with Discord</a>"

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

    # Use the token to get user guilds
    access_token = credentials.get("access_token")
    headers = {
        "Authorization": f"Bearer {access_token}"
    }
    guilds = requests.get("https://discord.com/api/users/@me/guilds", headers=headers).json()

    return jsonify(guilds)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
