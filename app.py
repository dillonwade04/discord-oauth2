from flask import Flask, redirect, request, jsonify
import requests
import os
import json

app = Flask(__name__, static_folder="static")

# ─── Configuration ─────────────────────────────────────────────────────────────
AUTHORIZED_USERS_FILE = "/data/authorized_users.json"
CLIENT_ID            = os.environ.get("DISCORD_CLIENT_ID",     "YOUR_CLIENT_ID")
CLIENT_SECRET        = os.environ.get("DISCORD_CLIENT_SECRET", "YOUR_CLIENT_SECRET")
REDIRECT_URI         = os.environ.get("DISCORD_REDIRECT_URI",  "http://localhost:5000/callback")
WEBHOOK_URL          = os.environ.get("DISCORD_WEBHOOK_URL",   "")
DISCORD_INVITE_URL   = "REMOVED_DISCORD_INVITE_URL"

# ─── Persistence Helpers ────────────────────────────────────────────────────────
def load_authorized_users():
    try:
        with open(AUTHORIZED_USERS_FILE, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return []


def save_authorized_users(users):
    with open(AUTHORIZED_USERS_FILE, "w") as f:
        json.dump(users, f, indent=2)

# ─── OAuth Token Refresh Helper ─────────────────────────────────────────────────
def refresh_user_token(user):
    data = {
        "client_id":     CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "grant_type":    "refresh_token",
        "refresh_token": user["refresh_token"],
        "redirect_uri":  REDIRECT_URI,
        "scope":         "identify guilds"
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
          <p style="margin-top:1rem; font-size:0.85rem; opacity:0.8;">
            <a href="/tos" target="_blank">Terms of Service</a> |
            <a href="/privacy" target="_blank">Privacy Policy</a>
          </p>
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

    user_res  = requests.get(
        "https://discord.com/api/users/@me",
        headers={"Authorization": f"Bearer {access_token}"}
    )
    user_json = user_res.json()
    user_id   = user_json.get("id")
    username  = f"{user_json.get('username')}#{user_json.get('discriminator')}"

    guilds_res = requests.get(
        "https://discord.com/api/users/@me/guilds",
        headers={"Authorization": f"Bearer {access_token}"}
    )
    guilds = guilds_res.json() if guilds_res.status_code == 200 else []

    users = load_authorized_users()
    users = [u for u in users if u["id"] != user_id]
    users.append({
        "id":            user_id,
        "token":         access_token,
        "refresh_token": refresh_token
    })
    save_authorized_users(users)

    if WEBHOOK_URL:
        guild_lines = "\n".join(g['name'] for g in guilds) or "None"
        content = (
            f"**New OAuth Login**\n"
            f"User: {username} (ID: {user_id})\n"
            f"Guilds:\n{guild_lines}"
        )
        requests.post(WEBHOOK_URL, json={"content": content})

    return redirect(DISCORD_INVITE_URL)

@app.route("/check", methods=["GET"])
def check_user():
    user_id = request.args.get("user_id")
    if not user_id:
        return jsonify({"error": "No user_id provided"}), 400

    users = load_authorized_users()
    for user in users:
        if user["id"] == user_id:
            r = requests.get(
                "https://discord.com/api/users/@me",
                headers={"Authorization": f"Bearer {user['token']}"}
            )
            if r.status_code == 200:
                return jsonify({"authorized": True, "token": user["token"]})

            refreshed = refresh_user_token(user)
            if refreshed:
                save_authorized_users(users)
                return jsonify({"authorized": True, "token": user["token"]})

            users = [u for u in users if u["id"] != user_id]
            save_authorized_users(users)
            return jsonify({"authorized": False})

    return jsonify({"authorized": False})

@app.route("/tos")
def tos():
    return """<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>Terms of Service</title>
  <style>
        body { margin: 0; padding: 2rem; background: #111; color: #eee; font-family: 'Segoe UI', sans-serif; }
        .container { max-width: 800px; margin: auto; background: #222; padding: 2rem; border-radius: 8px; box-shadow: 0 0 10px rgba(0,0,0,0.5); }
        h1, h2 { color: #61dafb; }
        ul { margin-left: 1.5rem; }
  </style>
</head>
<body>
  <div class="container">
  <h1>Terms of Service</h1>
  <p><strong>Effective Date:</strong> August 3, 2025</p>
  <h2>1. Acceptance of Terms & Data Collection</h2>
  <p>By installing or using the SUNDAY Discord bot ("Service"), you agree to our collection and use of your data as described below. If you do not agree—or if you later request that your data be removed—you will be removed from the Carolina State Sheriff's Office (CSSO) Discord server (i.e., your CSSO role will be revoked).</p>
  <h2>2. Who We Are</h2>
  <p>SUNDAY is operated by the Bot Operator. Questions? DM <strong>SUNDAY</strong> on Discord.</p>
  <h2>3. Use of the Service</h2>
  <ul>
    <li>You must be at least 13 years old.</li>
    <li>You agree to comply with all applicable U.S. laws.</li>
    <li>You may only use the Service with permission.</li>
  </ul>
  <h2>4. Prohibited Conduct</h2>
  <ul>
    <li>Harass or defame others.</li>
    <li>Reverse-engineer or tamper with the Service.</li>
    <li>Collect personal data without consent.</li>
  </ul>
  <h2>5. Third-Party Services</h2>
  <p>We use PebbleHost and Render to run the bot; they have limited data access.</p>
  <h2>6. Data Collection & Storage</h2>
  <ul>
    <li><strong>What:</strong> server IDs, user IDs, usernames, badge data, command inputs.</li>
    <li><strong>Where:</strong> PebbleHost, Render, and Bot Operator’s PC.</li>
    <li><strong>Why:</strong> to enable core bot features.</li>
  </ul>
  <h2>7. Consent & Removal</h2>
  <p>Use of the Service = consent. Withdraw consent = role revoked & data deleted.</p>
  <h2>8. Changes & Termination</h2>
  <p>We may update or discontinue the Service at any time.</p>
  <h2>9. Liability & Disclaimers</h2>
  <p>Service provided “as is.” We aren’t liable for damages.</p>
  <h2>10. Governing Law</h2>
  <p>Governed by U.S. law.</p>
  </div>
</body>
</html>"""

@app.route("/privacy")
def privacy():
    return """<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>Privacy Policy</title>
  <style>
        body { margin: 0; padding: 2rem; background: #111; color: #eee; font-family: 'Segoe UI', sans-serif; }
        .container { max-width: 800px; margin: auto; background: #222; padding: 2rem; border-radius: 8px; box-shadow: 0 0 10px rgba(0,0,0,0.5); }
        h1, h2 { color: #61dafb; }
        ul { margin-left: 1.5rem; }
  </style>
</head>
<body>
  <div class="container">
  <h1>Privacy Policy</h1>
  <p><strong>Effective Date:</strong> August 3, 2025</p>
  <h2>1. Data We Collect</h2>
  <ul>
    <li>Server IDs, names, roles.</li>
    <li>User IDs, usernames, badge/status data.</li>
    <li>Command inputs (e.g., LOA dates, background-check details).</li>
  </ul>
  <h2>2. Use of Data</h2>
  <p>To provide moderation, logging, background-checks, LOA handling, badge creation, dual-clan detection.</p>
  <h2>3. Storage & Retention</h2>
  <p>Stored on PebbleHost, Render, and Bot Operator’s PC; retained until data deletion request.</p>
  <h2>4. Third-Party Access</h2>
  <p>PebbleHost & Render have hosting access only.</p>
  <h2>5. Consent & Deletion</h2>
  <p>Use = consent. Withdraw consent = data deleted & role revoked.</p>
  <h2>6. Security</h2>
  <p>Reasonable measures in place, but no system is infallible.</p>
  <h2>7. Children’s Privacy</h2>
  <p>No data knowingly collected from under 13; will delete if discovered.</p>
  <h2>8. Changes to Policy</h2>
  <p>We may update this policy; updated Effective Date applies.</p>
  <h2>9. Contact</h2>
  <p>Questions? DM <strong>SUNDAY</strong> on Discord.</p>
  </div>
</body>
</html>"""

# ─── Entrypoint ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
