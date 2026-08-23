"""Guard against drift between pyproject.toml and the hash-pinned lockfiles.

``requirements.txt`` (runtime) and ``requirements-dev.txt`` (runtime + dev) are
generated with ``uv pip compile pyproject.toml ... --generate-hashes``. If a
dependency is added to or removed from ``pyproject.toml`` but the lockfiles are
not regenerated, CI/Docker installs silently diverge from what the project
declares -- the exact local-vs-CI drift (google-genai, PyJWT) this repo hit
before.

A lockfile is the *full transitive closure*, so it is a superset of the direct
dependencies. We therefore assert a subset relationship (every declared
dependency is present in the lock), not set equality, and compare at the
PEP 503-normalized name level -- versions are owned by the hash-pinned lock,
not by this test.

Stdlib only (``tomllib`` + ``re``) so the check adds no dependency and runs in
a bare environment.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PYPROJECT = REPO_ROOT / "pyproject.toml"
REQUIREMENTS = REPO_ROOT / "requirements.txt"
REQUIREMENTS_DEV = REPO_ROOT / "requirements-dev.txt"


def _normalize(name: str) -> str:
    """PEP 503 normalization: lowercase, collapse runs of -_. to a single -."""
    return re.sub(r"[-_.]+", "-", name).lower()


def _requirement_name(spec: str) -> str:
    """Extract the normalized package name from a PEP 508 requirement string.

    Handles extras and version specifiers, e.g. ``uvicorn[standard]>=0.24.0`` ->
    ``uvicorn`` and ``python-jose[cryptography]>=3.3.0`` -> ``python-jose``.
    """
    match = re.match(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)", spec)
    assert match, f"could not parse requirement name from: {spec!r}"
    return _normalize(match.group(1))


def _declared_names(section: list[str]) -> set[str]:
    return {_requirement_name(item) for item in section}


def _locked_names(lockfile: Path) -> set[str]:
    """Top-level pinned names from a ``uv pip compile`` lockfile.

    Package lines start in column 0 as ``name==version``; hashes, ``# via``
    comments, and continuations are indented, so a start-anchored match picks
    out exactly the pinned distributions.
    """
    names: set[str] = set()
    for line in lockfile.read_text().splitlines():
        match = re.match(r"^([A-Za-z0-9][A-Za-z0-9._-]*)==", line)
        if match:
            names.add(_normalize(match.group(1)))
    return names


def _load_pyproject() -> dict:
    with PYPROJECT.open("rb") as handle:
        return tomllib.load(handle)


def test_lockfiles_exist() -> None:
    assert REQUIREMENTS.is_file(), "requirements.txt (runtime lock) is missing"
    assert REQUIREMENTS_DEV.is_file(), "requirements-dev.txt (dev lock) is missing"


def test_runtime_deps_locked() -> None:
    """Every [project].dependencies entry must appear in requirements.txt."""
    declared = _declared_names(_load_pyproject()["project"]["dependencies"])
    missing = declared - _locked_names(REQUIREMENTS)
    assert not missing, (
        f"pyproject.toml runtime dependencies missing from requirements.txt: "
        f"{sorted(missing)}. Re-run: uv pip compile pyproject.toml "
        f"--python-version 3.12 --generate-hashes -o requirements.txt"
    )


def test_dev_deps_locked() -> None:
    """Every optional-dependencies.dev entry must appear in requirements-dev.txt."""
    dev = _load_pyproject()["project"]["optional-dependencies"]["dev"]
    missing = _declared_names(dev) - _locked_names(REQUIREMENTS_DEV)
    assert not missing, (
        f"pyproject.toml dev dependencies missing from requirements-dev.txt: "
        f"{sorted(missing)}. Re-run: uv pip compile pyproject.toml --extra dev "
        f"-c requirements.txt --python-version 3.12 --generate-hashes "
        f"-o requirements-dev.txt"
    )


def test_dev_lock_is_superset_of_runtime() -> None:
    """requirements-dev.txt is built with --extra dev, so it must contain every
    package the runtime lock does."""
    missing = _locked_names(REQUIREMENTS) - _locked_names(REQUIREMENTS_DEV)
    assert not missing, (
        f"requirements-dev.txt is missing runtime-locked packages "
        f"(the dev lock should be a superset): {sorted(missing)}"
    )
