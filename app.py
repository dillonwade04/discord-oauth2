"""Discord OAuth portal for the S.U.N.D.A.Y. bot ecosystem."""

from __future__ import annotations

import hmac
import json
import os
import secrets
from pathlib import Path

import requests
from flask import Flask, jsonify, redirect, render_template, request, session
from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")
DISCORD_API_URL = "https://discord.com/api"
REQUEST_TIMEOUT_SECONDS = 10


def required_env(name: str) -> str:
    """Return a required environment value or fail with a clear error."""
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Required environment variable {name} is not set")
    return value


CLIENT_ID = required_env("DISCORD_CLIENT_ID")
CLIENT_SECRET = required_env("DISCORD_CLIENT_SECRET")
REDIRECT_URI = os.getenv(
    "DISCORD_REDIRECT_URI", "http://localhost:5000/callback"
).strip()
DISCORD_INVITE_URL = required_env("DISCORD_INVITE_URL")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "").strip()
OAUTH_API_SECRET = required_env("OAUTH_API_SECRET")
FLASK_SECRET_KEY = required_env("FLASK_SECRET_KEY")
AUTHORIZED_USERS_FILE = Path(
    os.getenv(
        "AUTHORIZED_USERS_FILE",
        str(BASE_DIR / "data" / "authorized_users.json"),
    )
)


app = Flask(__name__, static_folder="static", template_folder="templates")
app.config.update(
    SECRET_KEY=FLASK_SECRET_KEY,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=REDIRECT_URI.lower().startswith("https://"),
)


def load_authorized_users() -> list[dict]:
    """Load stored Discord OAuth records from the private data volume."""
    try:
        with AUTHORIZED_USERS_FILE.open("r", encoding="utf-8") as file:
            data = json.load(file)
            return data if isinstance(data, list) else []
    except FileNotFoundError:
        return []
    except json.JSONDecodeError:
        app.logger.warning("Authorized-user data is not valid JSON")
        return []


def save_authorized_users(users: list[dict]) -> None:
    """Atomically save OAuth records outside version control."""
    AUTHORIZED_USERS_FILE.parent.mkdir(parents=True, exist_ok=True)
    temporary_file = AUTHORIZED_USERS_FILE.with_suffix(".json.tmp")
    temporary_file.write_text(json.dumps(users, indent=2), encoding="utf-8")
    temporary_file.replace(AUTHORIZED_USERS_FILE)


def valid_api_secret() -> bool:
    """Authenticate trusted callers of the token-check endpoint."""
    supplied_secret = request.headers.get("X-API-Key", "")
    return bool(supplied_secret) and hmac.compare_digest(
        supplied_secret, OAUTH_API_SECRET
    )


def refresh_user_token(user: dict) -> dict | None:
    """Refresh a stored Discord OAuth token, returning None on failure."""
    data = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "grant_type": "refresh_token",
        "refresh_token": user["refresh_token"],
        "redirect_uri": REDIRECT_URI,
        "scope": "identify guilds",
    }
    try:
        response = requests.post(
            f"{DISCORD_API_URL}/oauth2/token",
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
    except requests.RequestException:
        return None

    if response.status_code != 200:
        return None

    token_data = response.json()
    if "access_token" not in token_data:
        return None

    user["token"] = token_data["access_token"]
    user["refresh_token"] = token_data.get(
        "refresh_token", user["refresh_token"]
    )
    return user


@app.after_request
def add_security_headers(response):
    """Apply conservative browser and cache protections."""
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-Frame-Options"] = "DENY"
    if request.endpoint in {"callback", "check_user"}:
        response.headers["Cache-Control"] = "no-store"
    return response


@app.route("/")
def home():
    return render_template("home.html")


@app.route("/login")
def login():
    oauth_state = secrets.token_urlsafe(32)
    session["oauth_state"] = oauth_state
    params = {
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": "identify guilds",
        "state": oauth_state,
    }
    return redirect(
        f"{DISCORD_API_URL}/oauth2/authorize?{requests.compat.urlencode(params)}"
    )


@app.route("/callback")
def callback():
    expected_state = session.pop("oauth_state", None)
    received_state = request.args.get("state", "")
    if not expected_state or not hmac.compare_digest(expected_state, received_state):
        return "Invalid OAuth state", 400

    code = request.args.get("code")
    if not code:
        return "Error: no code provided", 400

    token_request = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT_URI,
        "scope": "identify guilds",
    }
    try:
        token_response = requests.post(
            f"{DISCORD_API_URL}/oauth2/token",
            data=token_request,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        token_data = token_response.json()
    except (requests.RequestException, ValueError):
        return "Discord authentication is temporarily unavailable", 502

    access_token = token_data.get("access_token")
    refresh_token = token_data.get("refresh_token")
    if not access_token or not refresh_token:
        return "Failed to retrieve access token", 502

    authorization_header = {"Authorization": f"Bearer {access_token}"}
    try:
        user_response = requests.get(
            f"{DISCORD_API_URL}/users/@me",
            headers=authorization_header,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        user_response.raise_for_status()
        user_data = user_response.json()

        guilds_response = requests.get(
            f"{DISCORD_API_URL}/users/@me/guilds",
            headers=authorization_header,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        guilds = guilds_response.json() if guilds_response.ok else []
    except (requests.RequestException, ValueError):
        return "Unable to retrieve Discord account information", 502

    user_id = user_data.get("id")
    if not user_id:
        return "Discord did not return a user ID", 502

    users = [user for user in load_authorized_users() if user.get("id") != user_id]
    users.append(
        {
            "id": user_id,
            "token": access_token,
            "refresh_token": refresh_token,
        }
    )
    save_authorized_users(users)

    if DISCORD_WEBHOOK_URL:
        username = user_data.get("global_name") or user_data.get("username", "Unknown")
        guild_lines = "\n".join(guild.get("name", "Unknown") for guild in guilds)
        content = (
            "**New OAuth Login**\n"
            f"User: {username} (ID: {user_id})\n"
            f"Guilds:\n{guild_lines or 'None'}"
        )
        try:
            requests.post(
                DISCORD_WEBHOOK_URL,
                json={"content": content},
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
        except requests.RequestException:
            app.logger.warning("Discord login webhook delivery failed")

    return redirect(DISCORD_INVITE_URL)


@app.route("/check", methods=["GET"])
def check_user():
    if not valid_api_secret():
        return jsonify({"error": "Unauthorized"}), 401

    user_id = request.args.get("user_id")
    if not user_id:
        return jsonify({"error": "No user_id provided"}), 400

    users = load_authorized_users()
    for user in users:
        if user.get("id") != user_id:
            continue

        try:
            response = requests.get(
                f"{DISCORD_API_URL}/users/@me",
                headers={"Authorization": f"Bearer {user['token']}"},
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
        except requests.RequestException:
            return jsonify({"error": "Discord API unavailable"}), 502

        if response.status_code == 200:
            return jsonify({"authorized": True, "token": user["token"]})

        refreshed_user = refresh_user_token(user)
        if refreshed_user:
            save_authorized_users(users)
            return jsonify({"authorized": True, "token": user["token"]})

        users = [stored_user for stored_user in users if stored_user.get("id") != user_id]
        save_authorized_users(users)
        return jsonify({"authorized": False})

    return jsonify({"authorized": False})


@app.route("/health")
def health():
    return jsonify({"status": "ok"})


@app.route("/tos")
def terms_of_service():
    return render_template("terms.html")


@app.route("/privacy")
def privacy_policy():
    return render_template("privacy.html")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
