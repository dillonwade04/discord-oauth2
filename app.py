from flask import Flask, redirect, request, jsonify
import requests
import os
import json

app = Flask(__name__, static_folder="static")

# ─── Configuration ─────────────────────────────────────────────────────────────
def _getenv(key, default=""):
    v = os.environ.get(key, default)
    return v.strip() if isinstance(v, str) else v

AUTHORIZED_USERS_FILE = _getenv("AUTHORIZED_USERS_FILE", "/data/authorized_users.json")
CLIENT_ID            = _getenv("DISCORD_CLIENT_ID",     "YOUR_CLIENT_ID")
CLIENT_SECRET        = _getenv("DISCORD_CLIENT_SECRET", "YOUR_CLIENT_SECRET")
REDIRECT_URI         = _getenv("DISCORD_REDIRECT_URI",  "http://localhost:5000/callback")
WEBHOOK_URL          = _getenv("DISCORD_WEBHOOK_URL",   "")
DISCORD_INVITE_URL   = _getenv("DISCORD_INVITE_URL",    "REMOVED_DISCORD_INVITE_URL")

# ─── Persistence Helpers ────────────────────────────────────────────────────────
def load_authorized_users():
    try:
        with open(AUTHORIZED_USERS_FILE, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return []


def save_authorized_users(users):
    try:
        dirname = os.path.dirname(AUTHORIZED_USERS_FILE)
        if dirname:
            os.makedirs(dirname, exist_ok=True)
        with open(AUTHORIZED_USERS_FILE, "w") as f:
            json.dump(users, f, indent=2)
    except Exception as e:
        app.logger.error("Failed to save authorized users: %s", e)

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
      <meta name="viewport" content="width=device-width, initial-scale=1.0">
      <title>CSSO OAuth</title>
      <style>
        body { font-family: system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif; margin:0; padding:0; background:#0b0b0f; color:#e8e8f0; }
        .wrap { max-width: 900px; margin: 0 auto; padding: 32px; }
        .hero { padding: 32px; border: 1px solid #23232b; border-radius: 16px; background: #13131a; }
        a.btn { background:#5865F2; color:white; padding:12px 18px; border-radius:10px; text-decoration:none; display:inline-block; }
        .small { color:#a5a7b3; font-size: 13px; }
        code { background:#191a22; padding:2px 6px; border-radius:6px; }
      </style>
    </head>
    <body>
      <div class="wrap">
        <div class="hero">
          <h1>Carolina State Sheriff’s Office – Auth</h1>
          <p>Login with Discord to verify and continue.</p>
          <p><a class="btn" href="/login">Login with Discord</a></p>
          <p class="small">Redirect URI in use: <code>""" + REDIRECT_URI + """</code></p>
          <p class="small"><a href="/terms">Terms</a> · <a href="/privacy">Privacy</a></p>
        </div>
      </div>
    </body>
    </html>
    """

@app.route("/login")
def login():
    app.logger.info("Using REDIRECT_URI=%s", REDIRECT_URI)
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
    token_res = requests.post("https://discord.com/api/oauth2/token", data=data, headers=headers, timeout=15)
    if token_res.status_code != 200:
        app.logger.error("OAuth token exchange failed: %s | %s", token_res.status_code, token_res.text)
        return f"OAuth token exchange failed: {token_res.text}", 400
    token_json = token_res.json()
    access_token  = token_json.get("access_token")
    refresh_token = token_json.get("refresh_token")
    if not access_token:
        app.logger.error("OAuth token response missing access_token: %s", token_res.text)
        return "OAuth token exchange failed: no access_token", 400

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
        try:
            requests.post(WEBHOOK_URL, json={"content": content}, timeout=10)
        except Exception as e:
            app.logger.warning("Webhook post failed: %s", e)

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
            # try refreshing
            new_user = refresh_user_token(user)
            if new_user:
                save_authorized_users([u if u["id"] != user_id else new_user for u in users])
                return jsonify({"authorized": True, "token": new_user["token"]})
            break

    return jsonify({"authorized": False}), 200

@app.route("/terms")
def terms():
    return """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<title>Terms of Service — CSSO Auth</title>
<meta name="viewport" content="width=device-width, initial-scale=1" />
<style>
  body { font-family: system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif; background:#0b0b0f; color:#e8e8f0; margin:0; }
  .wrap { max-width: 900px; margin:0 auto; padding:32px; }
  h1, h2 { color:#fff; }
  p, li { color:#c8cad6; line-height:1.6; }
  a { color:#9bb2ff; }
  code { background:#191a22; padding:2px 6px; border-radius:6px; }
  .card { background:#13131a; border:1px solid #23232b; border-radius:16px; padding:24px; }
</style>
</head>
<body>
  <div class="wrap card">
    <h1>Terms of Service</h1>
    <p><em>Effective Date: 2025-01-01</em></p>

    <p>Welcome to the Carolina State Sheriff’s Office (CSSO) Authentication Service (“Service”). These terms govern your access to and use of the Service.</p>

    <h2>1. Acceptance of Terms</h2>
    <p>By accessing or using the Service, you agree to these Terms. If you do not agree, do not use the Service.</p>

    <h2>2. Description of Service</h2>
    <p>The Service provides Discord OAuth-based authentication and basic verification to grant access to CSSO resources.</p>

    <h2>3. Eligibility</h2>
    <p>You must comply with Discord’s Terms and any CSSO rules. If you are under 13, you may not use the Service.</p>

    <h2>4. Prohibited Conduct</h2>
    <ul>
      <li>Harass, threaten, or defame others.</li>
      <li>Attempt to reverse-engineer, decompile, or tamper with the Service.</li>
      <li>Use the Service to collect personal data about others without their consent.</li>
      <li>Violate Discord’s Terms of Service or Community Guidelines.</li>
    </ul>

    <h2>5. Third-Party Services</h2>
    <p>We rely on hosting providers PebbleHost and Render to run the Service. These providers may have limited access to data solely to provide hosting and runtime.</p>

    <h2>6. Data Collection & Storage</h2>
    <ul>
      <li><strong>What we collect:</strong> server data (IDs, names), basic Discord profile info (user ID, username/global name), and voluntary form inputs (e.g. background-check details, LOA dates/reasons).</li>
      <li><strong>Storage:</strong> Minimal data stored in a JSON file for access control.</li>
      <li><strong>Retention:</strong> Data is retained only as long as necessary for operational purposes.</li>
    </ul>

    <h2>7. Disclaimers</h2>
    <p>The Service is provided “as is” without warranties of any kind.</p>

    <h2>8. Limitation of Liability</h2>
    <p>To the fullest extent permitted by law, CSSO shall not be liable for any indirect, incidental, special, consequential, or punitive damages.</p>

    <h2>9. Changes to These Terms</h2>
    <p>We may update these Terms; the “Effective Date” will change. Continued use after changes constitutes acceptance.</p>

    <h2>10. Contact</h2>
    <p>Questions? DM <strong>SUNDAY</strong> on Discord.</p>
  </div>
</body>
</html>
"""

@app.route("/privacy")
def privacy():
    return """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<title>Privacy Policy — CSSO Auth</title>
<meta name="viewport" content="width=device-width, initial-scale=1" />
<style>
  body { font-family: system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif; background:#0b0b0f; color:#e8e8f0; margin:0; }
  .wrap { max-width: 900px; margin:0 auto; padding:32px; }
  h1, h2 { color:#fff; }
  p, li { color:#c8cad6; line-height:1.6; }
  a { color:#9bb2ff; }
  code { background:#191a22; padding:2px 6px; border-radius:6px; }
  .card { background:#13131a; border:1px solid #23232b; border-radius:16px; padding:24px; }
</style>
</head>
<body>
  <div class="wrap card">
    <h1>Privacy Policy</h1>
    <p><em>Effective Date: 2025-01-01</em></p>

    <h2>1. Information We Collect</h2>
    <ul>
      <li>Discord user ID and basic profile info (username/global name).</li>
      <li>CSSO operational inputs you voluntarily submit (e.g. background-check form data, LOA dates/reasons).</li>
      <li>Server/guild metadata necessary to verify access.</li>
    </ul>

    <h2>2. How We Use Information</h2>
    <ul>
      <li>Authenticate users and grant CSSO access.</li>
      <li>Audit, security, and abuse prevention.</li>
      <li>Compliance with platform and community rules.</li>
    </ul>

    <h2>3. Sharing</h2>
    <p>We do not sell your data. Limited sharing occurs only with service providers (hosting/runtime) and when required by law.</p>

    <h2>4. Data Security</h2>
    <p>We use reasonable measures to protect data. No method of transmission or storage is 100% secure.</p>

    <h2>5. Data Retention</h2>
    <p>We keep data only as long as needed for the purposes above, then delete it.</p>

    <h2>6. Your Choices</h2>
    <p>You may request access or deletion of your data by contacting the CSSO admins.</p>

    <h2>7. Children’s Privacy</h2>
    <p>We do not knowingly collect data from anyone under 13. If we discover such data, we will delete it.</p>

    <h2>8. Changes</h2>
    <p>We may update this Privacy Policy; the “Effective Date” will change. Continued use after changes constitutes acceptance.</p>

    <h2>9. Contact</h2>
    <p>For questions or requests, send a direct message to <strong>SUNDAY</strong> on Discord.</p>
  </div>
</body>
</html>
"""

# ─── Health ────────────────────────────────────────────────────────────────────
@app.route("/health")
def health():
    return jsonify({"status":"ok", "redirect_uri": REDIRECT_URI}), 200

# ─── Entrypoint ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
