"""ASGI wrapper for Vercel functions.

Vercel expects a top-level function under `api/`. This file exposes the
existing FastAPI `app` from `src/api.py` so the deployment builder can
detect and start the application.
"""
from src import api as api_module

# Expose `app` object for Vercel's ASGI entrypoint
app = api_module.app
