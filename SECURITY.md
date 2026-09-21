# Security policy

Do not open a public issue containing a Discord client secret, OAuth token,
webhook URL, private invite, shared API secret, Flask secret key, or exported
authorization record.

If a credential is exposed, revoke or rotate it at the issuing service. Removing
it from the latest commit is not sufficient because Git retains prior history.

The authorization store contains Discord access and refresh tokens. Keep it on
a private persistent volume, restrict filesystem access, exclude it from
backups that are not encrypted, and never serve it through the application’s
static directory.

Trusted clients must authenticate to `/check` with the `X-API-Key` header over
HTTPS. Use separate, high-entropy values for `OAUTH_API_SECRET` and
`FLASK_SECRET_KEY`.
