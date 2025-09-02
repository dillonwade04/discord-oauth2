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

    try:
        token_json = token_res.json()
    except Exception as e:
        return f"Failed to parse token response: {e}\n\nRaw response:\n{token_res.text}", 500

    if "error" in token_json:
        return f"Discord OAuth error: {token_json['error_description']}", 400

    access_token  = token_json.get("access_token")
    refresh_token = token_json.get("refresh_token")

    if not access_token:
        return f"Failed to retrieve access token.\nResponse: {token_json}", 500

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
    ul, ol { margin-left: 1.5rem; }
  </style>
</head>
<body>
  <div class="container">
    <h1>Terms of Service</h1>
    <p><strong>Effective Date:</strong> August 3, 2025</p>

    <h2>1. Acceptance of Terms & Data Collection</h2>
    <p>By installing or using the SUNDAY Discord bot (“Service”), you agree to our collection and use of your data as described below. If you do <strong>not</strong> agree—or if you later request that your data be removed—you will be removed from the Carolina State Sheriff’s Office (CSSO) Discord server (i.e., your CSSO role will be revoked). If you do not agree, do not use the Service.</p>

    <h2>2. Who We Are</h2>
    <p>SUNDAY is operated by the Bot Operator (“we,” “us,” “our”). Questions? Send a direct message to <strong>SUNDAY</strong> on Discord.</p>

    <h2>3. Use of the Service</h2>
    <ul>
      <li>You must be at least 13 years old.</li>
      <li>You agree to comply with all applicable U.S. federal, state, and local laws.</li>
      <li>You may only use the Service on servers where you have permission.</li>
    </ul>

    <h2>4. Prohibited Conduct</h2>
    <ul>
      <li>Harass, threaten, or defame others.</li>
      <li>Attempt to reverse-engineer, decompile, or tamper with the Service.</li>
      <li>Use the Service to collect personal data about others without their consent.</li>
      <li>Violate Discord’s Terms of Service or Community Guidelines.</li>
    </ul>

    <h2>5. Third-Party Services</h2>
    <p>We rely on hosting providers PebbleHost and Render to run the bot. They have limited access to data solely to provide hosting and runtime.</p>

    <h2>6. Data Collection & Storage</h2>
    <ul>
      <li><strong>What we collect:</strong> server data (IDs, names, roles), user IDs, usernames, badge/status data, command inputs (e.g. background-check details, LOA dates/reasons).</li>
      <li><strong>Where it’s stored:</strong> PebbleHost, Render, and the Bot Operator’s personal PC.</li>
      <li><strong>Why we collect it:</strong> to enable bot features (moderation, logging, background checks, LOA handling, badge creation, dual-clan detection, OAuth guild fetch).</li>
    </ul>

    <h2>7. Consent & Removal</h2>
    <p>Your use of the Service constitutes consent to this data collection. If you request deletion of your data—or otherwise withdraw consent—we will revoke your CSSO role and remove your access to the CSSO server.</p>

    <h2>8. Modifications & Termination</h2>
    <p>We may modify or discontinue the Service (or these Terms) at any time. Continued use after changes constitutes acceptance. We reserve the right to suspend or terminate your access for violations.</p>

    <h2>9. Disclaimers</h2>
    <p>The Service is provided “as is,” without warranties of any kind. We do not guarantee uptime, accuracy, or fitness for any particular purpose.</p>

    <h2>10. Limitation of Liability</h2>
    <p>In no event will we be liable for indirect, incidental, special, or consequential damages arising from your use of the Service.</p>

    <h2>11. Indemnification</h2>
    <p>You agree to defend and indemnify us against any claims, damages, or losses arising from your violation of these Terms.</p>

    <h2>12. Governing Law</h2>
    <p>These Terms are governed by U.S. law, without regard to conflict-of-law principles.</p>
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
    ul, ol { margin-left: 1.5rem; }
  </style>
</head>
<body>
  <div class="container">
    <h1>Privacy Policy</h1>
    <p><strong>Effective Date:</strong> August 3, 2025</p>

    <h2>1. Introduction</h2>
    <p>This Privacy Policy explains how SUNDAY (“we,” “us,” “our”) collects, uses, and shares your information when you use our Discord bot (“Service”).</p>

    <h2>2. Information We Collect</h2>
    <ul>
      <li><strong>Server Data:</strong> server ID, name, roles.</li>
      <li><strong>User Data:</strong> Discord user ID, username, badge/status data.</li>
      <li><strong>Command Inputs:</strong> any free-text or option data you submit (e.g., background-check Steam hex, LOA dates/reasons).</li>
    </ul>

    <h2>3. How We Use Your Information</h2>
    <ul>
      <li>To enable core features: moderation, logging, background-check workflows, leave-of-absence handling, badge creation, dual-clan detection.</li>
      <li>To troubleshoot issues and improve the Service.</li>
      <li>To comply with legal obligations.</li>
    </ul>

    <h2>4. Data Storage & Retention</h2>
    <p><strong>Storage Locations:</strong> PebbleHost, Render, and the Bot Operator’s personal PC.<br>
    <strong>Retention Period:</strong> Data is kept as long as you remain on the CSSO server or until you request deletion.</p>

    <h2>5. Third-Party Access</h2>
    <p>PebbleHost and Render have access solely to host and run the bot. We do not sell or rent your data.</p>

    <h2>6. Consent & Deletion</h2>
    <ol>
      <li>Remove your data from all active systems.</li>
      <li>Revoke your CSSO role, removing your access to the CSSO Discord server.</li>
    </ol>

    <h2>7. Security</h2>
    <p>We implement reasonable measures to protect your data. However, no system is completely secure—use at your own risk.</p>

    <h2>8. Children’s Privacy</h2>
    <p>We do not knowingly collect data from anyone under 13. If we discover such data, we will delete it.</p>

    <h2>9. Changes to This Policy</h2>
    <p>We may update this Privacy Policy; the “Effective Date” will change. Continued use after changes constitutes acceptance.</p>

    <h2>10. Contact Us</h2>
    <p>For questions or requests, send a direct message to <strong>SUNDAY</strong> on Discord.</p>
  </div>
</body>
</html>"""

# ─── Entrypoint ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
