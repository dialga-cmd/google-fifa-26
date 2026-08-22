"""
FanWayfinder Authentication Utilities - Extracted from src/api.py
"""

import jwt
from datetime import datetime, timedelta, timezone
from typing import Optional

from .config import Config
from jose import JWTError


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Create a JWT access token."""
    to_encode = data.copy()
    issued_at = datetime.now(timezone.utc)
    if expires_delta:
        expire = issued_at + expires_delta
    else:
        expire = issued_at + timedelta(minutes=Config.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"iat": issued_at, "exp": expire})
    try:
        encoded_jwt = jwt.encode(to_encode, Config.SECRET_KEY, algorithm="HS256")
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.error(f"JWT encoding error: {e}")
        raise
    return encoded_jwt


def verify_token(token: str) -> Optional[TokenData]:
    """Verify a JWT token and return the payload if valid."""
    try:
        payload = jwt.decode(token, Config.SECRET_KEY, algorithms=["HS256"])
        from .config import TokenData
        token_data = TokenData(
            username=payload.get("sub"),
            exp=payload.get("exp")
        )
        return token_data
    except jwt.JWTError as e:
        logger = logging.getLogger(__name__)
        logger.warning(f"JWT validation failed: {e}")
        return None
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.error(f"Unexpected error during token verification: {e}")
        return None