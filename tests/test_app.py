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

    def test_check_rejects_wrong_secret_without_reading_tokens(self):
        from unittest.mock import patch
        with patch.object(oauth_app, "load_authorized_users") as load:
            response = self.client.get("/check?user_id=123", headers={"X-API-Key": "wrong"})
        self.assertEqual(response.status_code, 401)
        load.assert_not_called()

    def test_login_webhook_disables_mentions(self):
        from unittest.mock import Mock, patch
        self.client.get("/login")
        with self.client.session_transaction() as stored:
            state = stored["oauth_state"]
        token = Mock(json=Mock(return_value={"access_token": "fake", "refresh_token": "fake-refresh"}))
        user = Mock(json=Mock(return_value={"id": "123", "username": "@everyone"}))
        guilds = Mock(ok=True, json=Mock(return_value=[{"name": "@here"}]))
        with patch.object(oauth_app, "DISCORD_WEBHOOK_URL", "https://example.invalid/webhook"), patch.object(oauth_app.requests, "get", side_effect=[user, guilds]), patch.object(oauth_app.requests, "post", side_effect=[token, Mock()]) as post:
            response = self.client.get("/callback", query_string={"code": "fake", "state": state})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(post.call_args.kwargs["json"]["allowed_mentions"], {"parse": []})
        self.assertLessEqual(len(post.call_args.kwargs["json"]["content"]), 2000)

    def test_check_endpoint_accepts_trusted_caller(self):
        response = self.client.get(
            "/check?user_id=123",
            headers={"X-API-Key": "test-api-secret"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {"authorized": False})


class TokenStorageTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.original_file = oauth_app.AUTHORIZED_USERS_FILE
        oauth_app.AUTHORIZED_USERS_FILE = Path(self.directory.name) / 'private' / 'authorized_users.json'

    def tearDown(self):
        oauth_app.AUTHORIZED_USERS_FILE = self.original_file
        self.directory.cleanup()

    @unittest.skipUnless(os.name == 'posix', 'POSIX filesystem permissions')
    def test_private_permissions_survive_replacement(self):
        import stat
        old = os.umask(0o022)
        try:
            for i in range(2):
                oauth_app.upsert_authorized_user({'id': str(i), 'token': 'fake', 'refresh_token': 'fake'})
                self.assertEqual(stat.S_IMODE(oauth_app.AUTHORIZED_USERS_FILE.stat().st_mode), 0o600)
                self.assertEqual(stat.S_IMODE(oauth_app.AUTHORIZED_USERS_FILE.parent.stat().st_mode), 0o700)
        finally:
            os.umask(old)

    def test_concurrent_workers_do_not_lose_records(self):
        import subprocess
        import sys
        env = dict(os.environ, AUTHORIZED_USERS_FILE=str(oauth_app.AUTHORIZED_USERS_FILE))
        script = "import app,sys; [app.upsert_authorized_user({'id':sys.argv[1]+'-'+str(i), 'token':'fake', 'refresh_token':'fake'}) for i in range(5)]"
        workers = [subprocess.Popen([sys.executable, '-c', script, str(i)], env=env,
                                   cwd=oauth_app.BASE_DIR, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                   for i in range(8)]
        try:
            for worker in workers:
                out, err = worker.communicate(timeout=30)
                self.assertEqual(worker.returncode, 0, err.decode())
        finally:
            for worker in workers:
                if worker.poll() is None:
                    worker.kill()
                    worker.wait()
        self.assertEqual(len(oauth_app.load_authorized_users()), 40)

    def test_corrupt_store_is_not_silently_overwritten(self):
        oauth_app.prepare_private_store()
        oauth_app.AUTHORIZED_USERS_FILE.write_text('broken json')
        with self.assertRaises(ValueError):
            oauth_app.upsert_authorized_user({'id': 'test', 'token': 'fake', 'refresh_token': 'fake'})
        self.assertEqual(oauth_app.AUTHORIZED_USERS_FILE.read_text(), 'broken json')

    def test_public_storage_directory_is_rejected(self):
        oauth_app.AUTHORIZED_USERS_FILE = oauth_app.BASE_DIR / 'static' / 'tokens.json'
        with self.assertRaises(RuntimeError):
            oauth_app.prepare_private_store()


if __name__ == "__main__":
    unittest.main()
