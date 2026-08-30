"""Production SECRET_KEY enforcement in src/config.py.

The insecure ``secrets.token_hex(32)`` fallback was removed. In production the
``SECRET_KEY`` environment variable must be set to a strong, unique value and
the app refuses to start otherwise (checked at startup via
``Config.validate_production_config()``, called from the FastAPI lifespan).
Outside production a fixed, clearly-insecure development default is used so
local dev and the test suite can run.
"""

import os
import sys
from contextlib import contextmanager

import pytest

# Add src to path (mirrors the other test modules).
sys.path.insert(0, "src")

from config import Config, _DEV_SECRET_KEY


@contextmanager
def _env(**overrides):
    """Snapshot os.environ, apply overrides (value None deletes the key), restore."""
    original = dict(os.environ)
    try:
        for key, value in overrides.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        yield
    finally:
        os.environ.clear()
        os.environ.update(original)


def test_random_default_secret_attribute_removed():
    """The random per-process _DEFAULT_SECRET_KEY fallback no longer exists."""
    assert not hasattr(Config, "_DEFAULT_SECRET_KEY")


def test_dev_secret_key_is_fixed_stable_value():
    """Confirm _DEV_SECRET_KEY is a fixed stable value (not random per import)."""
    assert isinstance(_DEV_SECRET_KEY, str)
    assert _DEV_SECRET_KEY == "dev-insecure-do-not-use-in-production"


def test_dev_secret_key_stable_across_imports():
    """Confirm _DEV_SECRET_KEY is identical across fresh imports (not regenerated)."""
    import sys
    # Import config module fresh
    if "config" in sys.modules:
        del sys.modules["config"]
    import config as config_first
    key1 = config_first._DEV_SECRET_KEY

    # Import again fresh
    if "config" in sys.modules:
        del sys.modules["config"]
    import config as config_second
    key2 = config_second._DEV_SECRET_KEY

    # Both imports should yield the exact same fixed value
    assert key1 == key2 == "dev-insecure-do-not-use-in-production"


def test_production_without_secret_key_raises():
    with _env(ENVIRONMENT="production", SECRET_KEY=None):
        with pytest.raises(
            ValueError, match="SECRET_KEY must be explicitly set in production"
        ):
            Config.validate_production_config()


def test_production_with_dev_default_secret_raises():
    with _env(ENVIRONMENT="production", SECRET_KEY=_DEV_SECRET_KEY):
        with pytest.raises(ValueError, match="insecure development default"):
            Config.validate_production_config()


def test_production_with_real_secret_passes():
    with _env(ENVIRONMENT="production", SECRET_KEY="a-strong-unique-production-secret"):
        Config.validate_production_config()  # must not raise


def test_non_production_without_secret_key_is_allowed():
    with _env(ENVIRONMENT="development", SECRET_KEY=None):
        Config.validate_production_config()  # must not raise


def test_missing_environment_var_defaults_to_non_production():
    """No ENVIRONMENT set behaves as development: no enforcement."""
    with _env(ENVIRONMENT=None, SECRET_KEY=None):
        Config.validate_production_config()  # must not raise
