from flask import Flask, redirect, request, jsonify
import requests
import os
import json
from datetime import datetime

app = Flask(__name__, static_folder="static")

# ─── Config ───────────────────────────────────────────────────────────────────
AUTHORIZED_USERS_FILE = "/data/authorized_users.json"
CLIENT_ID            = os.environ.get("DISCORD_CLIENT_ID",      "YOUR_CLIENT_ID")
CLIENT_SECRET        = os.environ.get("DISCORD_CLIENT_SECRET",  "YOUR_CLIENT_SECRET")
REDIRECT_URI         = os.environ.get("DISCORD_REDIRECT_URI",   "http://localhost:5000/callback")
WEBHOOK_URL          = os.environ.get("DISCORD_WEBHOOK_URL",    "").rstrip("/")
DISCORD_INVITE_URL   = "REMOVED_DISCORD_INVITE_URL"

# ─── Storage Helpers ───────────────────────────────────────────────────────────
def load_authorized_users():
    try:
        with open(AUTHORIZED_USERS_FILE, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return []

def save_authorized_users(users):
    with open(AUTHORIZED_USERS_FILE, "w") as f:
        json.dump(users, f, indent=2)

# ─── Token Refresh Helper ───────────────────────────────────────────────────────
def refresh_user_token(user):
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
    user["refresh_token"] = tok.get("refresh_token", user["refresh_token"])
    return user

# ─── Routes ────────────────────────────────────────────────────────────────────

@app.route("/")
def home():
    # Your original inline HTML + CSS homepage
    return """
    <html>
    <head>
      <link rel="icon" type="image/x-icon" href="/static/favicon.ico">
      <title>Carolina State Sheriff's Office</title>
      <style>
        body {
          margin: 0; padding: 0; height: 100vh;
          background: url('/static/cssobanner.gif') no-repeat center center fixed;
          background-size: cover;
          font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
          color: #fff; overflow: hidden;
        }
        .overlay {
          position: absolute; top: 0; left: 0; right: 0; bottom: 0;
          background: rgba(0,0,0,0.7);
        }
        .content {
          position: relative; z-index: 2;
          display: flex; align-items: center; justify-content: center;
          height: 100vh; text-align: center;
        }
        .card {
          background: rgba(0,0,0,0.6);
          backdrop-filter: blur(10px);
          padding: 2rem 3rem;
          border-radius: 16px;
          box-shadow: 0 8px 32px rgba(0,0,0,0.5);
          max-width: 360px; width: 90%;
        }
        .logo { width: 80px; margin-bottom: 1rem; }
        h2 { margin: 0.5rem 0; font-size: 1.5rem; }
        p  { margin: 0.5rem 0 1rem; opacity: 0.85; }
        .discord-logo {
          display: block; width: 60px; margin: 1rem auto; opacity: 0.8;
        }
        .login-btn {
          display: inline-block; padding: 0.75rem 2rem; font-size: 1rem;
          text-transform: uppercase; letter-spacing: 1px;
          background: linear-gradient(135deg,#7289da 0%,#99a7f2 100%);
          color:#fff; border:none; border-radius:8px;
          text-decoration:none;
          box-shadow:0 0 15px rgba(114,137,218,0.7);
          transition:box-shadow .3s ease,transform .2s ease;
        }
        .login-btn:hover {
          box-shadow:0 0 25px rgba(114,137,218,0.9);
          transform: translateY(-2px);
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
          <img class="discord-logo" src="/static/discord.png" alt="Discord Logo">
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

    # 1) Exchange code for token
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

    # 2) Fetch user info
    user_res  = requests.get(
        "https://discord.com/api/users/@me",
        headers={"Authorization": f"Bearer {access_token}"}
    )
    user_json = user_res.json()
    user_id   = user_json.get("id")
    username  = f"{user_json.get('username')}#{user_json.get('discriminator')}"

    # 3) Fetch their guilds
    guilds_res = requests.get(
        "https://discord.com/api/users/@me/guilds",
        headers={"Authorization": f"Bearer {access_token}"}
    )
    guilds = guilds_res.json() if guilds_res.status_code == 200 else []

    # 4) Save/update in JSON store
    users = load_authorized_users()
    users = [u for u in users if u["id"] != user_id]
    users.append({
        "id":            user_id,
        "token":         access_token,
        "refresh_token": refresh_token
    })
    save_authorized_users(users)

    # 5) Send “New OAuth Login” embed via your webhook
    if WEBHOOK_URL:
        # Build the embed payload
        embed_payload = {
            "embeds": [{
                "title":     "New OAuth Login",
                "color":     0x7289DA,
                "timestamp": datetime.utcnow().isoformat(),
                "fields": [
                    {"name": "User",   "value": f"{username} (ID: {user_id})", "inline": False},
                    {"name": "Guilds", "value": "\n".join(g["name"] for g in guilds) or "None", "inline": False}
                ]
            }]
        }

        # DEBUG: print to your container logs
        print("[DEBUG] WEBHOOK_URL =", WEBHOOK_URL)
        print("[DEBUG] Payload:", embed_payload)

        try:
            resp = requests.post(WEBHOOK_URL, json=embed_payload, timeout=5)
            print(f"[DEBUG] Webhook POST returned {resp.status_code}: {resp.text}")
        except Exception as e:
            print(f"[ERROR] Exception sending webhook: {e}")

    # 6) Finally, redirect back to your Discord invite
    return redirect(DISCORD_INVITE_URL)

@app.route("/check", methods=["GET"])
def check_user():
    user_id = request.args.get("user_id")
    if not user_id:
        return jsonify({"error": "No user_id provided"}), 400

    users = load_authorized_users()
    for user in users:
        if user["id"] == user_id:
            # Test current token
            r = requests.get(
                "https://discord.com/api/users/@me",
                headers={"Authorization": f"Bearer {user['token']}"}
            )
            if r.status_code == 200:
                return jsonify({"authorized": True, "token": user["token"]})

            # Try refreshing if expired
            refreshed = refresh_user_token(user)
            if refreshed:
                save_authorized_users(users)
                return jsonify({"authorized": True, "token": user["token"]})

            # Otherwise evict
            users = [u for u in users if u["id"] != user_id]
            save_authorized_users(users)
            return jsonify({"authorized": False})

    return jsonify({"authorized": False})

# ─── Run ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
