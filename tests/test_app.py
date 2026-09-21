import os
import tempfile
import unittest
from pathlib import Path
from urllib.parse import parse_qs, urlparse


os.environ.setdefault("DISCORD_CLIENT_ID", "test-client-id")
os.environ.setdefault("DISCORD_CLIENT_SECRET", "test-client-secret")
os.environ.setdefault("DISCORD_REDIRECT_URI", "http://localhost:5000/callback")
os.environ.setdefault("DISCORD_INVITE_URL", "https://example.invalid/invite")
os.environ.setdefault("OAUTH_API_SECRET", "test-api-secret")
os.environ.setdefault("FLASK_SECRET_KEY", "test-flask-secret")

import app as oauth_app


class AppSmokeTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        oauth_app.AUTHORIZED_USERS_FILE = (
            Path(self.temporary_directory.name) / "authorized_users.json"
        )
        oauth_app.app.config.update(TESTING=True)
        self.client = oauth_app.app.test_client()

    def tearDown(self):
        self.temporary_directory.cleanup()

    def test_public_pages_and_health(self):
        for path in ("/", "/tos", "/privacy", "/health"):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 200)

    def test_login_includes_oauth_state(self):
        response = self.client.get("/login")
        self.assertEqual(response.status_code, 302)
        query = parse_qs(urlparse(response.location).query)
        self.assertEqual(query["client_id"], ["test-client-id"])
        self.assertTrue(query.get("state"))

    def test_callback_rejects_invalid_state(self):
        response = self.client.get("/callback?code=test&state=incorrect")
        self.assertEqual(response.status_code, 400)

    def test_check_endpoint_requires_api_secret(self):
        response = self.client.get("/check?user_id=123")
        self.assertEqual(response.status_code, 401)

    def test_check_endpoint_accepts_trusted_caller(self):
        response = self.client.get(
            "/check?user_id=123",
            headers={"X-API-Key": "test-api-secret"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {"authorized": False})


if __name__ == "__main__":
    unittest.main()
