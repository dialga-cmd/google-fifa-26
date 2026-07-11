"""
Lightweight local JWT shim for tests.

Provides minimal `encode`, `decode`, and `JWTError` compatible with tests
that import `jwt`. This avoids requiring PyJWT in the test environment.

Note: This implementation does NOT perform signature verification and is
meant only for testing purposes where tests call `jwt.decode(...,
options={"verify_signature": False})`.
"""
from __future__ import annotations

import base64
import json
import hmac
import hashlib
import datetime as _dt
from typing import Any, Dict, Optional


class JWTError(Exception):
    pass


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode('ascii').rstrip('=')


def _b64url_decode(data: str) -> bytes:
    padding = '=' * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def encode(payload: Dict[str, Any], key: Optional[str] = None, algorithm: str = 'HS256') -> str:
    """Encode a JWT without a real signature (test shim).

    Produces a three-part JWT (header.payload.signature) where signature
    is an empty string placeholder. Header/ payload are base64url-encoded.
    """
    header = {'alg': algorithm, 'typ': 'JWT'}

    # Convert non-serializable types (e.g., datetime) to numeric timestamps
    serializable_payload = {}
    for k, v in payload.items():
        if isinstance(v, _dt.datetime):
            # Convert to POSIX timestamp (int)
            serializable_payload[k] = int(v.timestamp())
        else:
            serializable_payload[k] = v

    h_b = _b64url_encode(json.dumps(header, separators=(',', ':'), sort_keys=True).encode('utf-8'))
    p_b = _b64url_encode(json.dumps(serializable_payload, separators=(',', ':'), sort_keys=True).encode('utf-8'))

    signing_input = f"{h_b}.{p_b}".encode('utf-8')
    key_bytes = (key or '').encode('utf-8')

    # Only HS256 is supported in this shim
    if algorithm.upper() != 'HS256':
        raise JWTError('Only HS256 is supported by the test shim')

    sig_bytes = hmac.new(key_bytes, signing_input, hashlib.sha256).digest()
    sig = _b64url_encode(sig_bytes)
    return f"{h_b}.{p_b}.{sig}"


def decode(token: str, options: Optional[Dict[str, Any]] = None, **kwargs) -> Dict[str, Any]:
    """Decode JWT and return payload dict.

    If `options` includes `verify_signature` set to False, the payload is
    returned without verifying the signature. If `verify_signature` is
    True (or omitted), this shim will raise JWTError because it does not
    perform signature verification.
    """
    if not token or token.count('.') != 2:
        raise JWTError('Invalid token format')

    header_b, payload_b, signature_b = token.split('.', 2)

    verify = True
    if options and isinstance(options, dict):
        verify = bool(options.get('verify_signature', True))

    if verify:
        # Verify signature using provided key (from kwargs)
        key = kwargs.get('key') or kwargs.get('secret') or None
        if not key:
            # Try 'options' may include 'verify_signature' only; require explicit key
            raise JWTError('No key provided for signature verification')
        signing_input = f"{header_b}.{payload_b}".encode('utf-8')
        expected_sig = _b64url_encode(hmac.new(str(key).encode('utf-8'), signing_input, hashlib.sha256).digest())
        if signature_b != expected_sig:
            raise JWTError('Signature verification failed')

    try:
        payload_json = _b64url_decode(payload_b).decode('utf-8')
        return json.loads(payload_json)
    except Exception as exc:
        raise JWTError(f'Failed to decode token payload: {exc}')
