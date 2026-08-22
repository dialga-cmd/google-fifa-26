"""
FanWayfinder Configuration - Extracted from src/api.py
"""

import json
import logging
import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Set
from pydantic import BaseModel, Field, field_validator

logger = logging.getLogger(__name__)


def load_env_file() -> None:
    dotenv_path = Path(__file__).resolve().parent.parent / '.env'
    if not dotenv_path.exists():
        return

    logger = logging.getLogger(__name__)
    try:
        with open(dotenv_path, 'r', encoding='utf-8') as handle:
            for line in handle:
                line = line.strip()
                if not line or line.startswith('#') or '=' not in line:
                    continue
                key, value = line.split('=', 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = value
        logger.info('Loaded environment variables from %s', dotenv_path)
    except Exception as exc:
        logger.warning('Could not load .env file: %s', exc)


load_env_file()


class Config:
    _DEFAULT_SECRET_KEY = os.getenv("SECRET_KEY", secrets.token_hex(32))
    MQTT_BROKER = os.getenv("MQTT_BROKER", "test.mosquitto.org")
    MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
    MQTT_TOPIC = os.getenv("MQTT_TOPIC", "stadium/congestion/edge/#")
    KNOWLEDGE_BASE_FILE = os.getenv("KB_FILE", "data/kb_chunks.json")
    STADIUM_GRAPH_FILE = os.getenv("GRAPH_FILE", "data/stadium_graph.gexf")
    DEFAULT_LOCATION = os.getenv("DEFAULT_LOCATION", "Gate_A")
    MAX_QUERY_LENGTH = int(os.getenv("MAX_QUERY_LENGTH", "200"))
    CACHE_SIZE = int(os.getenv("CACHE_SIZE", "128"))
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    GROQ_API_KEY = os.getenv("GROQ_API_KEY")
    AI_PROVIDER = os.getenv("AI_PROVIDER", "auto")
    # Security settings
    SECRET_KEY = os.getenv("SECRET_KEY", _DEFAULT_SECRET_KEY)  # fallback for dev only
    ACCESS_TOKEN_EXPIRE_MINUTES = int(
        os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30")
    )
    # Rate limiting
    RATE_LIMIT_REQUESTS = int(os.getenv("RATE_LIMIT_REQUESTS", "30"))
    RATE_LIMIT_WINDOW = int(os.getenv("RATE_LIMIT_WINDOW", "60"))  # seconds
    # Advice cache (Redis) settings
    REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
    REDIS_DB = int(os.getenv("REDIS_DB", "0"))
    REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", None)
    # Allowed languages (ISO 639-1)
    ALLOWED_LANGUAGES = {"en", "es", "fr", "de", "zh", "ar", "ru"}
    FIFA_STADIUMS = {
        "MetLife Stadium",
        "SoFi Stadium",
        "AT&T Stadium",
        "Mercedes-Benz Stadium",
        "Gillette Stadium",
        "Lumen Field",
        "Hard Rock Stadium",
        "Levi's Stadium",
        "NRG Stadium",
        "Arrowhead Stadium",
        "Lucas Oil Stadium",
        "Rose Bowl",
        "BMO Field",
        "BC Place",
        "Commonwealth Stadium",
        "Estadio Azteca",
    }
    DEFAULT_STADIUM = "MetLife Stadium"

    @classmethod
    def validate_production_config(cls):
        """Validate that required configuration is set for production."""
        if os.getenv("ENVIRONMENT", "development").lower() == "production":
            if "SECRET_KEY" not in os.environ or not os.getenv("SECRET_KEY"):
                if cls.SECRET_KEY != cls._DEFAULT_SECRET_KEY:
                    raise ValueError("SECRET_KEY must be explicitly set in production")
                raise ValueError("Missing required environment variables for production: SECRET_KEY")
            secret_key = os.getenv("SECRET_KEY") or cls.SECRET_KEY
            if not secret_key or secret_key in {"mocked_default", "mock-secret-key"}:
                raise ValueError("SECRET_KEY must be explicitly set in production")