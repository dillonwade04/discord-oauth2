# S.U.N.D.A.Y. Discord OAuth Portal

A compact Flask service that handles Discord OAuth for the S.U.N.D.A.Y. bot
ecosystem. Users authenticate with Discord, the service stores refreshable
OAuth credentials on a private persistent volume, and trusted bot services can
check an authorization record through a protected internal endpoint.

## Features

- Discord OAuth authorization-code flow with `state` validation
- Private, configurable storage for access and refresh tokens
- Automatic refresh of expired Discord access tokens
- Shared-secret authentication for the internal `/check` endpoint
- Optional Discord webhook notifications after a successful login
- Responsive portal, Terms of Service, and Privacy Policy templates
- Health endpoint and automated route/security smoke tests

## Project structure

```text
.
|-- .github/workflows/ci.yml  # Automated tests and syntax checks
|-- static/                   # Styles, logos, and portal artwork
|-- templates/                # Flask HTML templates
|-- tests/                    # Offline smoke tests
|-- app.py                    # Application and OAuth routes
|-- Procfile                  # Gunicorn process declaration
|-- .env.example              # Safe configuration template
`-- requirements.txt          # Pinned Python dependencies
```

## Local setup

1. Create and activate a virtual environment.

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

2. Install dependencies.

   ```powershell
   python -m pip install -r requirements.txt
   ```

3. Copy the environment template and replace every placeholder.

   ```powershell
   Copy-Item .env.example .env
   ```

4. Add the exact callback URL from `DISCORD_REDIRECT_URI` to the OAuth2 section
   of your Discord application settings.

5. Start the local development server.

   ```powershell
   python app.py
   ```

The portal will be available at `http://localhost:5000` by default.

## Environment variables

| Variable | Required | Purpose |
| --- | --- | --- |
| `DISCORD_CLIENT_ID` | Yes | Public identifier for the Discord OAuth application |
| `DISCORD_CLIENT_SECRET` | Yes | Authenticates OAuth token exchanges |
| `DISCORD_REDIRECT_URI` | Yes in production | OAuth callback registered with Discord |
| `DISCORD_INVITE_URL` | Yes | Destination after successful authorization |
| `DISCORD_WEBHOOK_URL` | No | Sends a login notification to Discord |
| `OAUTH_API_SECRET` | Yes | Authenticates trusted callers of `/check` |
| `FLASK_SECRET_KEY` | Yes | Signs the OAuth state session cookie |
| `AUTHORIZED_USERS_FILE` | No | Private token-store path; defaults to `data/authorized_users.json` |
| `PORT` | No | HTTP port; defaults to `5000` |

Generate independent random values for `OAUTH_API_SECRET` and
`FLASK_SECRET_KEY`. Never reuse the Discord client secret for either purpose.

## Endpoints

| Route | Purpose |
| --- | --- |
| `GET /` | Portal landing page |
| `GET /login` | Begins Discord OAuth |
| `GET /callback` | Validates and completes Discord OAuth |
| `GET /check?user_id=...` | Trusted authorization lookup; requires `X-API-Key` |
| `GET /health` | Hosting health check |
| `GET /tos` | Terms of Service |
| `GET /privacy` | Privacy Policy |

`/check` is an internal service endpoint because a successful response may
contain a short-lived Discord access token. Only trusted backend services should
receive `OAUTH_API_SECRET`, and the service should always be deployed behind
HTTPS.

## Deployment

The included `Procfile` starts the service with Gunicorn:

```text
web: gunicorn app:app
```

Configure all required environment variables in the hosting platform and mount
a private persistent volume for `AUTHORIZED_USERS_FILE`. Do not place the token
store inside a publicly served directory or commit it to Git.

## Testing

```powershell
python -m unittest discover -s tests -v
python -m compileall -q app.py tests
```

## Security

See [SECURITY.md](SECURITY.md). Public repository visibility does not grant
permission to reuse the code; no software license is included at this time.
