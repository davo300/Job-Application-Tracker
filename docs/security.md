# Authentication and security

Implemented in milestone 2. These controls follow the
[OWASP session guidance](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html)
and [CSRF guidance](https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html).

## Passwords

Use Argon2id via `argon2-cffi`'s PasswordHasher defaults, including random salts.
Registration accepts 12–128 characters without trimming the password. There
are no arbitrary symbol/composition requirements. Login verifies the existing
hash and upgrades its parameters when the library recommends a rehash.
Unknown accounts also perform hash verification and receive the same 401 error
as an incorrect password. This reduces, but does not eliminate, timing signals.
Duplicate registration returns 409, which can reveal account existence; the
registration throttle limits abuse. Email verification would enable a more
private registration workflow later.

Pydantic SecretStr protects model representations. The custom validation error
handler removes raw inputs and exception context from responses so malformed
password fields are never echoed. Never log request bodies or token headers.

## Sessions

Generate independent 256-bit random session and CSRF tokens. Store SHA-256
digests in PostgreSQL; raw tokens exist only in cookies. Fast hashing is
appropriate for high-entropy tokens, unlike human-chosen passwords.

Each successful login/registration creates fresh tokens and revokes the previous
session presented by that browser. Other devices stay signed in. Sessions have
a fixed 24-hour lifetime by default, configurable from 1–168 hours. Expiry is
checked server-side. Logout deletes the session immediately and expires both
cookies. Successful authentication removes expired session rows.

The session cookie is HttpOnly, SameSite=Lax, host scoped, and Path=/. Production
adds Secure and the `__Host-` prefix; the CSRF cookie has the same scope but is
readable by JavaScript. Authentication tokens never enter localStorage or API
JSON responses. Production settings reject HTTP origins; deploy behind HTTPS.

## CSRF and request origins

All unsafe HTTP methods require `X-Requested-With: job-tracker`. When supplied,
Origin must exactly match the configured allowlist; cross-site Fetch Metadata
is also rejected. No CORS permission is granted. A foreign site cannot send
this custom header through a browser without a successful preflight. This also
protects unauthenticated login and registration from login CSRF.

Authenticated mutation routes must additionally depend on `CurrentUser`, which
checks `X-CSRF-Token` against the current session's stored digest with a
constant-time comparison. The frontend reads only the CSRF cookie and attaches
this header. A token from another session is rejected. XSS remains a threat;
CSRF protection does not defend against malicious scripts running on our origin.

CLI API consumers must send the custom request header and maintain a cookie jar;
logout additionally requires the CSRF token. Swagger alone cannot submit unsafe
requests without the required header; use the frontend or an HTTP client.

## Ownership

`GET /auth/me` derives identity exclusively from the verified session. Never
accept a user-supplied user ID as the authority for resource access. Future CRUD
routes must use CurrentUser, scope repository queries to that user's ID, and
return 404 for resources belonging to another account. Existing composite
foreign keys additionally prevent cross-account references in the database.

## Rate limits and remaining work

Login and registration share a bounded, thread-safe per-client-IP throttle:
20 attempts per 60 seconds per API process by default. Denials return 429 and a
Retry-After header. The application uses the ASGI client address; configure
trusted proxy forwarding carefully. Vite proxy traffic can share one address,
which is acceptable for local development.

Before a production launch, implement a shared ingress limiter if using multiple
workers/instances, email verification and password recovery, security monitoring,
TLS, and tested backups. The current limiter is not distributed and is reset
on process restart. Account settings, password changes, logout-all-devices,
and account deletion are not implemented.
