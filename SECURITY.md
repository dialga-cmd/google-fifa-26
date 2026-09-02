# Security

This document describes FanWayfinder's real trust boundaries and how secrets,
tokens, and external data actually flow, based on the code in this repository
(`src/api.py`, `src/config.py`, `api/advice.py`) — not a generic template.

FanWayfinder began as a hackathon project. Several controls are deliberately
relaxed for demo use and are called out explicitly below under **Current posture
& known limitations**. Read that section before deploying anywhere that handles
real users or real secrets.

## Components and trust boundaries

```
            (untrusted, public internet)
                        │
        ┌───────────────┼─────────────────────────┐
        │               │                          │
   Fan browser     MQTT publishers            (operators)
        │          (public broker)                 │
        │ HTTPS          │ MQTT (plaintext, no auth)
        ▼                ▼                          
┌─────────────────────────────────────────────────┐
│  FanWayfinder FastAPI app  (single deployment)   │  ← trust boundary
│                                                   │
│  • Serves the frontend same-origin               │
│    (GET /, /app.js, /style.css)                   │
│  • /advice, /token, /stadiums endpoints           │
│  • In-memory advice cache + lru_cache             │
│  • In-process MQTT client → routing graph         │
│  • Reads all config from environment variables    │
└───────────────┬───────────────────────┬──────────┘
                │ HTTPS (egress)         │ HTTPS (egress)
                ▼                        ▼
          Groq API                  Google Gemini API
   api.groq.com/.../completions    (google-genai SDK)
   Authorization: Bearer <key>     Client(api_key=<key>)
```

The trust boundary is the FastAPI process. Everything outside it — the fan's
browser, MQTT publishers, and the Groq/Gemini APIs — is untrusted or
third-party. The frontend is **not** a separate host: `src/api.py` serves
`frontend/index.html`, `app.js`, and `style.css` from the same origin, so there
is no cross-origin boundary between frontend and backend and (by design) no CORS
middleware is configured.

## Secrets management

- **All configuration is read from environment variables** in `src/config.py`
  via `os.getenv`. There are no secrets hardcoded in the source.
- **Secrets must come from the platform's environment** (e.g. the Render
  dashboard's environment variables) and must **never** be committed. `.env` is
  gitignored; `.env.example` in the repo holds placeholders only and is the
  canonical list of every variable the app reads.
- For local development, `load_env_file()` (in `src/config.py`) optionally reads
  a local `.env` and only sets keys that are not already in the environment, so
  real platform env vars always win.
- **`SECRET_KEY` is required in every environment — there is no fallback.**
  `src/config.py` fails fast at import time when `SECRET_KEY` is unset, and
  `Config.validate_production_config()` re-checks at application startup (the
  FastAPI `lifespan` hook in `src/api.py`). Neither a fixed dev default nor a
  random per-process fallback exists: a hardcoded secret is a scanner-flagged
  security risk, and a random value would silently invalidate tokens across
  restarts/workers while masking the misconfiguration.

Secret-bearing variables (see `.env.example`): `SECRET_KEY`, `GEMINI_API_KEY`,
`GROQ_API_KEY`, and `REDIS_PASSWORD`.

## Authentication and JWT flow

- `POST /token` issues a JWT via `create_access_token()`: signed with
  `Config.SECRET_KEY` using **HS256** (a symmetric secret — anyone with
  `SECRET_KEY` can mint valid tokens, so it is a high-value secret), carrying
  `sub`, `iat`, and `exp` claims, expiring after `ACCESS_TOKEN_EXPIRE_MINUTES`
  (default 30).
- `verify_token()` decodes and validates signature and expiry, returning the
  claims or `None` on failure.
- Route protection is provided by `verify_token_dependency` over
  `HTTPBearer(auto_error=False)`.

## AI provider calls (data egress)

`generate_ai_response()` in `src/api.py` sends the **user's query text** (wrapped
in a system prompt loaded from `prompts/stadium_assistant_prompt.txt`) to an
external AI provider selected by `AI_PROVIDER` (`auto`/`groq`/`gemini`):

- **Groq**: `httpx.post` to `https://api.groq.com/openai/v1/chat/completions`
  with `Authorization: Bearer <GROQ_API_KEY>`.
- **Gemini**: the `google-genai` SDK client constructed with
  `api_key=<GEMINI_API_KEY>` (model `gemini-3.6-flash`).

Implications: (1) query content leaves the trust boundary and is processed under
the third party's terms — do not send data you are not permitted to share with
Groq/Google; (2) the API keys are bearer credentials that grant billable access
to those accounts and must be protected accordingly. Both providers are optional
— if no key is configured the app degrades to its local knowledge base/graph.

## MQTT congestion feed (untrusted data ingress)

`MQTTHandler` in `src/api.py` connects to `Config.MQTT_BROKER`
(default `test.mosquitto.org:1883`) and subscribes to
`stadium/congestion/edge/#`, folding received updates into the in-memory routing
graph. By default this is a **public broker with no authentication and no TLS**,
so incoming congestion data is untrusted and, on the default broker, publishable
by anyone. Messages are parsed defensively (failures are logged, not fatal), but
the *values* are not authenticated. For any real deployment, point `MQTT_BROKER`
at a private, authenticated, TLS-enabled broker.

## Caching

Caching is **in-process only**: a `functools.lru_cache` lookup and a custom
in-memory `AdviceCache` (a TTL dict) in `src/api.py`. No advice or user data is
written to Redis. The `REDIS_HOST`/`REDIS_PORT`/`REDIS_DB`/`REDIS_PASSWORD`
variables exist in `Config` but are **not currently wired to any Redis client**;
the only place a Redis URL is actually consumed is the optional
`SLOWAPI_STORAGE_URI` used as the rate-limiter's storage backend (defaults to
`memory://`).

## HTTP hardening in place

- **Security headers** are added to every response by an HTTP middleware in
  `src/api.py`: `Strict-Transport-Security`, `X-Content-Type-Options: nosniff`,
  `X-Frame-Options: DENY`, `X-XSS-Protection`, a restrictive
  `Content-Security-Policy` (`default-src 'self'`, `frame-ancestors 'none'`,
  etc.), and `Referrer-Policy`.
- **Rate limiting** via `slowapi`, keyed by client IP
  (`get_remote_address`), default `RATE_LIMIT_REQUESTS`/`RATE_LIMIT_WINDOW`
  (30 requests / 60 s).
- **Input validation** via Pydantic request models plus allowlists in `Config`
  (`ALLOWED_LANGUAGES`, `FIFA_STADIUMS`, `MAX_QUERY_LENGTH`) and validation of
  `location` against the known graph nodes.

## Current posture & known limitations

These are intentional hackathon-era relaxations. Harden them before any
production or public deployment:

- **Authentication is optional and non-enforcing.** `HTTPBearer` is created with
  `auto_error=False`, and `verify_token_dependency` returns `None` (allowing the
  request) both when no token is supplied **and** when a supplied token is
  invalid. Endpoints using it therefore do not actually reject unauthenticated
  or bad-token requests today.
- **`/token` accepts any username/password.** There is no user store or password
  verification; it mints a token for whatever username is posted.
- **`TrustedHostMiddleware` allows all hosts** (`allowed_hosts=["*"]`). Set this
  to your real hostname(s) in production.
- **Rate-limit storage is in-memory by default**, which is per-process and does
  not hold across multiple workers/instances. Set `SLOWAPI_STORAGE_URI` to a
  shared backend for multi-worker deployments.
- **The default MQTT broker is public and unauthenticated** (see above).

Production hardening checklist: enforce auth (raise on missing/invalid tokens),
back `/token` with a real user store, restrict `allowed_hosts`, set
`ENVIRONMENT=production` with a strong `SECRET_KEY`, use a private TLS MQTT
broker, and terminate TLS at the platform (Render) so `Strict-Transport-Security`
is meaningful.

## Reporting a vulnerability

Please report security issues privately to the repository owner (via the
repository's private contact channel or a direct message) rather than opening a
public issue, and allow reasonable time for a fix before any public disclosure.
Do not include real secrets or personal data in a report.
