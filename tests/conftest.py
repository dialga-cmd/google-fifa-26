"""Pytest configuration for the FanWayfinder suite.

``src/config.py`` now fails fast at import when ``SECRET_KEY`` is unset, in
every environment, so the suite provides a dedicated test key before any module
under test is imported. Contributors can run ``pytest`` without exporting
anything; this key is only ever used for the local test run and never in
production.
"""
import os

os.environ.setdefault(
    "SECRET_KEY", "pytest-suite-only-test-secret-key-not-for-production"
)
