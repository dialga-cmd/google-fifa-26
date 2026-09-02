"""SECRET_KEY is required in every environment — no fallback.

The fixed insecure development default (``_DEV_SECRET_KEY``) and any random
at-import fallback are gone. The ``SECRET_KEY`` environment variable must be
explicitly set before the package is imported, and the startup re-check
``Config.validate_production_config()`` refuses to proceed without it in every
``ENVIRONMENT``.

Import-path behavior is exercised in real subprocesses (with a deliberately
empty ``SECRET_KEY``, which an eventual ``SECRET_KEY=`` line in a local .env can
never restore), so the tests are hermetic and don't depend on the repo's
private .env.
"""

import os
import subprocess
import sys

import pytest

# Add src to path (mirrors the other test modules).
sys.path.insert(0, "src")

from config import Config  # noqa: E402  (requires SECRET_KEY from tests/conftest.py)

_SRC_DIR = os.path.join(os.path.dirname(__file__), "..", "src")


def _run_config_probe(code: str, environment, secret: str) -> subprocess.CompletedProcess:
    """Run ``code`` in a subprocess importing src/config under a controlled env.

    ``secret=""`` simulates "no SECRET_KEY": the empty string is falsy and, being
    already present in os.environ, cannot be overwritten by ``load_env_file``.
    """
    env = dict(os.environ)
    env["SECRET_KEY"] = secret
    if environment is None:
        env.pop("ENVIRONMENT", None)
    else:
        env["ENVIRONMENT"] = environment
    env["PYTHONPATH"] = _SRC_DIR
    return subprocess.run(
        [sys.executable, "-c", code],
        cwd=os.path.dirname(_SRC_DIR),
        env=env,
        capture_output=True,
        text=True,
    )


@pytest.mark.parametrize(
    "environment", ["production", "development", "testing", "staging", None]
)
def test_import_requires_secret_key_in_every_environment(environment):
    """Importing config with SECRET_KEY unset fails fast, whatever ENVIRONMENT."""
    result = _run_config_probe("import config", environment=environment, secret="")
    assert result.returncode != 0
    assert "SECRET_KEY" in result.stderr
    assert "no fallback" in result.stderr


@pytest.mark.parametrize(
    "environment", ["production", "development", "testing", "staging", None]
)
def test_import_accepts_explicit_secret_key_in_every_environment(environment):
    """An explicitly-set SECRET_KEY lets config import in every environment."""
    result = _run_config_probe(
        "import config; print(config.Config.SECRET_KEY)",
        environment=environment,
        secret="explicit-test-secret-key-value",
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "explicit-test-secret-key-value"


def test_no_secret_fallback_attribute_remains():
    """Neither a fixed dev default nor a random fallback constant exists anymore."""
    result = _run_config_probe(
        "import config; "
        "assert not hasattr(config, '_DEV_SECRET_KEY'); "
        "assert not hasattr(config, '_DEFAULT_SECRET_KEY'); "
        "assert not hasattr(config.Config, '_DEFAULT_SECRET_KEY'); "
        "print('clean')",
        environment="development",
        secret="probe-key-value",
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "clean"


@pytest.mark.parametrize(
    "environment", ["production", "development", "testing", None]
)
def test_validate_config_requires_secret_key_in_every_environment(environment):
    """Startup re-check raises when SECRET_KEY is missing in any environment."""
    original = dict(os.environ)
    try:
        if environment is None:
            os.environ.pop("ENVIRONMENT", None)
        else:
            os.environ["ENVIRONMENT"] = environment
        os.environ.pop("SECRET_KEY", None)
        with pytest.raises(ValueError, match="SECRET_KEY"):
            Config.validate_production_config()
    finally:
        os.environ.clear()
        os.environ.update(original)


@pytest.mark.parametrize(
    "environment", ["production", "development", "testing", None]
)
def test_validate_config_accepts_explicit_secret_key_in_every_environment(environment):
    """Startup re-check passes once SECRET_KEY is explicitly set."""
    original = dict(os.environ)
    try:
        if environment is None:
            os.environ.pop("ENVIRONMENT", None)
        else:
            os.environ["ENVIRONMENT"] = environment
        os.environ["SECRET_KEY"] = "a-strong-unique-secret-value"
        Config.validate_production_config()  # must not raise
    finally:
        os.environ.clear()
        os.environ.update(original)
