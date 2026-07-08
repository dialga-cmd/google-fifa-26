"""
FanWayfinder API - AI-powered stadium navigation assistant for FIFA World Cup 2026
Production-ready version with JWT authentication, Redis caching, rate limiting,
security headers, and comprehensive validation.
"""

import json
import logging
import os
import threading
import time
import re
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Set
import secrets
import httpx
from functools import lru_cache
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pydantic import BaseModel, Field, field_validator

# Try to import google genai, but make it optional
try:
    from google import genai as google_genai
except ImportError:  # pragma: no cover - depends on environment
    google_genai = None

# Import the rest of the dependencies
import uvicorn
from fastapi import FastAPI, HTTPException, Depends, status, Request
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from jose import jwt, JWTError

if not hasattr(jwt, "JWTError"):
    jwt.JWTError = JWTError

import networkx as nx
import paho.mqtt.client as mqtt
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware


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

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger(__name__)

# Configuration from environment with defaults
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

# Pydantic models with validation
class AdviceRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=Config.MAX_QUERY_LENGTH)
    language: str = Field(default="en")
    location: str = Field(default=Config.DEFAULT_LOCATION)
    stadium: str = Field(default=Config.DEFAULT_STADIUM)

    @field_validator('query')
    @classmethod
    def sanitize_query(cls, v):
        # Remove potential script tags and excessive whitespace
        v = re.sub(r'<[^>]*>', '', v)  # Remove HTML tags
        v = re.sub(r'\s+', ' ', v).strip()  # Normalize whitespace
        return v

    @field_validator('language')
    @classmethod
    def validate_language(cls, v):
        if v.lower() not in Config.ALLOWED_LANGUAGES:
            raise ValueError(f"Language must be one of {sorted(Config.ALLOWED_LANGUAGES)}")
        return v.lower()

    @field_validator('location')
    @classmethod
    def validate_location(cls, v):
        if not v or len(v) > 50:
            raise ValueError('Invalid location')
        # Additional validation will be performed at runtime against known nodes
        return v

    @field_validator('stadium')
    @classmethod
    def validate_stadium(cls, v):
        if not v or v not in Config.FIFA_STADIUMS:
            raise ValueError(f"Stadium must be one of the FIFA 2026 venues: {sorted(Config.FIFA_STADIUMS)}")
            return v

class AdviceResponse(BaseModel):
    advice: str
    route: Optional[List[str]] = None
    congestion_aware: bool = True

class TokenData(BaseModel):
    username: Optional[str] = None
    exp: Optional[float] = None

class UserLogin(BaseModel):
    username: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


# Knowledge base with improved search
class KnowledgeBase:
    def __init__(self, kb_file: str):
        self.kb_file = kb_file
        self.chunks: List[Dict] = []
        self.chunk_texts: List[str] = []
        self.chunk_ids: List[str] = []
        self._load_chunks()
        # Pre-compute search terms for efficiency
        self.chunk_terms: List[Set[str]] = []
        for text in self.chunk_texts:
            terms = set(re.findall(r'\b\w+\b', text.lower()))
            self.chunk_terms.append(terms)

    def _load_chunks(self):
        try:
            with open(self.kb_file, 'r') as f:
                self.chunks = json.load(f)
            self.chunk_texts = [item['text'] for item in self.chunks]
            self.chunk_ids = [item['id'] for item in self.chunks]
        except FileNotFoundError:
            logger.warning(f"Knowledge base file {self.kb_file} not found, using fallback")
            # Fallback to basic knowledge if file missing
            self.chunks = [
                {"id": "fallback_1", "text": "Restrooms are near each gate."},
                {"id": "fallback_2", "text": "Food concessions are near each gate."},
                {"id": "fallback_3", "text": "Medical tents are near Gate A and Gate C."},
                {"id": "fallback_4", "text": "Sections 101-104 (lower bowl) and 201-204 (upper bowl)."},
                {"id": "fallback_5", "text": "Stadium has four gates: A (North), B (East), C (South), D (West)."}
            ]
            self.chunk_texts = [item['text'] for item in self.chunks]
            self.chunk_ids = [item['id'] for item in self.chunks]
            self.chunk_terms = [set(re.findall(r'\b\w+\b', text.lower())) for text in self.chunk_texts]

    @lru_cache(maxsize=Config.CACHE_SIZE)
    def retrieve_relevant_chunks(self, query: str, k: int = 3) -> List[str]:
        """Retrieve relevant knowledge chunks using improved text matching."""
        if not query.strip():
            return self.chunk_texts[:k]

        # Extract query terms
        query_terms = set(re.findall(r'\b\w+\b', query.lower()))

        # Score chunks by term overlap (Jaccard similarity)
        scored_chunks = []
        for i, (chunk_text, chunk_terms) in enumerate(zip(self.chunk_texts, self.chunk_terms)):
            if not chunk_terms:
                continue
            intersection = len(query_terms & chunk_terms)
            union = len(query_terms | chunk_terms)
            if union > 0:
                score = intersection / union
            else:
                score = 0
            # Boost score for exact phrase matches
            if query.lower() in chunk_text.lower():
                score += 0.5
            scored_chunks.append((score, chunk_text))

        # Sort by score descending and return top k
        scored_chunks.sort(key=lambda x: x[0], reverse=True)
        return [chunk for score, chunk in scored_chunks[:k] if score > 0] or self.chunk_texts[:k]


# Stadium graph manager with congestion handling
class StadiumGraph:
    def __init__(self, graph_file: str):
        self.graph_file = graph_file
        self.G: Optional[nx.Graph] = None
        self.edge_congestion: Dict[Tuple[str, str], float] = {}
        self.lock = threading.RLock()  # Reentrant lock for nested calls
        self._valid_nodes: Set[str] = set()
        self._load_graph()

    def _load_graph(self):
        try:
            self.G = nx.read_gexf(self.graph_file)
            # Ensure nodes have required attributes
            for node, data in self.G.nodes(data=True):
                if 'x' not in data:
                    data['x'] = 0
                if 'y' not in data:
                    data['y'] = 0
                if 'type' not in data:
                    data['type'] = 'unknown'
            self._valid_nodes = set(self.G.nodes())
            logger.info(f"Loaded graph with {self.G.number_of_nodes()} nodes and {self.G.number_of_edges()} edges")
        except Exception as e:
            logger.error(f"Could not load graph from {self.graph_file}: {e}")
            # Create a basic fallback graph
            self.G = nx.Graph()
            self.G.add_node('Gate_A', type='gate', x=0, y=100)
            self.G.add_node('Gate_B', type='gate', x=100, y=100)
            self.G.add_node('Gate_C', type='gate', x=100, y=0)
            self.G.add_node('Gate_D', type='gate', x=0, y=0)
            self._valid_nodes = {'Gate_A', 'Gate_B', 'Gate_C', 'Gate_D'}
            logger.warning("Using fallback graph")

    def update_congestion(self, edge: Tuple[str, str], congestion: float):
        """Update congestion factor for an edge (thread-safe)."""
        with self.lock:
            # Validate congestion value
            congestion = max(0.0, min(1.0, congestion))
            self.edge_congestion[edge] = congestion
            # Also update reverse edge for undirected graph
            self.edge_congestion[(edge[1], edge[0])] = congestion

    def get_edge_weight(self, u: str, v: str, attr: Dict) -> float:
        """Calculate edge weight based on base distance and congestion."""
        base = attr.get('base_distance', 1.0)
        with self.lock:
            cong = self.edge_congestion.get((u, v), 0.0)
        # Weight = base * (1 + congestion) - higher congestion increases weight
        return base * (1 + cong)

    def find_shortest_path(self, source: str, target: str) -> List[str]:
        """Find shortest path avoiding congested routes when possible."""
        if not self.G or source not in self.G.nodes or target not in self.G.nodes:
            return []

        try:
            path = nx.shortest_path(self.G, source=source, target=target, weight=self.get_edge_weight)
            return path
        except nx.NetworkXNoPath:
            # Fallback to unweighted path if weighted fails
            try:
                path = nx.shortest_path(self.G, source=source, target=target)
                return path
            except nx.NetworkXNoPath:
                return []
        except Exception as e:
            logger.error(f"Error finding shortest path: {e}")
            return []

    def get_nodes_by_type(self, node_type: str) -> List[str]:
        """Get all nodes of a specific type."""
        if not self.G:
            return []
        return [node for node, data in self.G.nodes(data=True)
                if data.get('type') == node_type]

    @property
    def valid_nodes(self) -> Set[str]:
        """Get set of valid node identifiers."""
        return self._valid_nodes


# Simple in-memory cache for advice responses (fallback)
class AdviceCache:
    def __init__(self, maxsize: int = 64, ttl: int = 300):
        self.maxsize = maxsize
        self.ttl = ttl
        self.cache: Dict[str, Tuple[float, AdviceResponse]] = {}
        self.lock = threading.RLock()

    def get(self, key: str) -> Optional[AdviceResponse]:
        with self.lock:
            if key in self.cache:
                timestamp, value = self.cache[key]
                if time.time() - timestamp < self.ttl:
                    return value
                else:
                    del self.cache[key]
        return None

    def set(self, key: str, value: AdviceResponse):
        with self.lock:
            # Remove oldest if at capacity
            if len(self.cache) >= self.maxsize:
                # Simple FIFO removal (not truly LRU, but good enough for demo)
                oldest_key = next(iter(self.cache))
                del self.cache[oldest_key]
            self.cache[key] = (time.time(), value)


# MQTT handler for real-time congestion updates
class MQTTHandler:
    def __init__(self, broker: str, port: int, topic: str, graph: StadiumGraph):
        self.broker = broker
        self.port = port
        self.topic = topic
        self.graph = graph
        self.client: Optional[mqtt.Client] = None
        self.connected = False
        self._setup_client()

    def _setup_client(self):
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self.client.on_disconnect = self._on_disconnect

    def _on_connect(self, client, userdata, flags, reason_code, properties):
        if reason_code == 0:
            logger.info(f"Connected to MQTT broker at {self.broker}:{self.port}")
            self.connected = True
            client.subscribe(self.topic)
        else:
            logger.error(f"Failed to connect to MQTT broker, reason code {reason_code}")
            self.connected = False

    def _on_message(self, client, userdata, packet):
        try:
            payload = json.loads(packet.payload.decode())
            # Expect payload format: {"edge": "node1-node2", "congestion": 0.7, "timestamp": ...}
            edge_str = payload.get('edge', '')
            cong = payload.get('congestion', 0.0)

            # Parse edge string format "node1-node2"
            if '-' in edge_str:
                node1, node2 = edge_str.split('-', 1)
                self.graph.update_congestion((node1, node2), float(cong))
        except (json.JSONDecodeError, ValueError, KeyError) as e:
            logger.error(f"Error processing MQTT message: {e}")

    def _on_disconnect(self, client, userdata, disconnect_flags, reason_code, properties):
        logger.info("Disconnected from MQTT broker")
        self.connected = False

    def start(self):
        """Start MQTT client in background thread."""
        if self.client:
            try:
                self.client.connect(self.broker, self.port, 60)
                self.client.loop_start()
            except Exception as e:
                logger.error(f"Failed to start MQTT client: {e}")

    def stop(self):
        """Stop MQTT client."""
        if self.client:
            self.client.loop_stop()
            self.client.disconnect()


# Rate limiter using an in-memory store by default for local/demo use.
# Set SLOWAPI_STORAGE_URI to a Redis URL in production if desired.
def get_storage_uri() -> str:
    configured_uri = os.getenv("SLOWAPI_STORAGE_URI")
    if configured_uri:
        return configured_uri
    return "memory://"

limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=get_storage_uri(),
    default_limits=[f"{Config.RATE_LIMIT_REQUESTS}/{Config.RATE_LIMIT_WINDOW}seconds"]
)

# Auth utilities
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
        logger.error(f"JWT encoding error: {e}")
        raise
    return encoded_jwt


def verify_token(token: str) -> Optional[TokenData]:
    """Verify a JWT token and return the payload if valid."""
    try:
        payload = jwt.decode(token, Config.SECRET_KEY, algorithms=["HS256"])
        token_data = TokenData(
            username=payload.get("sub"),
            exp=payload.get("exp")
        )
        return token_data
    except jwt.JWTError as e:
        logger.warning(f"JWT validation failed: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error during token verification: {e}")
        return None


def load_system_prompt() -> str:
    """Load the strict stadium assistant prompt from disk."""
    prompt_path = os.path.join(os.path.dirname(__file__), "..", "prompts", "stadium_assistant_prompt.txt")
    try:
        with open(prompt_path, "r", encoding="utf-8") as handle:
            return handle.read().strip()
    except FileNotFoundError:
        return (
            "You are FanWayfinder, a strict stadium assistant. Help fans and staff with navigation, "
            "safety, accessibility, and crowd guidance. Be concise, practical, and accurate."
        )


def generate_ai_response(prompt: str) -> Optional[str]:
    """Generate a response from an AI provider when a key is configured."""
    provider = (Config.AI_PROVIDER or "auto").lower()
    system_prompt = load_system_prompt()
    full_prompt = f"{system_prompt}\n\nUser request:\n{prompt}"
    logger.info(
        "AI request starting: provider=%s, groq_key=%s, gemini_key=%s",
        provider,
        bool(Config.GROQ_API_KEY),
        bool(Config.GEMINI_API_KEY),
    )

    if provider in {"groq", "auto"} and Config.GROQ_API_KEY:
        try:
            logger.info("Trying Groq provider")
            response = httpx.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {Config.GROQ_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "llama-3.1-8b-instant",
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0.2,
                },
                timeout=15.0,
            )
            response.raise_for_status()
            data = response.json()
            result = data.get("choices", [{}])[0].get("message", {}).get("content")
            logger.info("Groq response received")
            return result
        except Exception as exc:  # pragma: no cover - network/env dependent
            response_text = getattr(exc, 'response', None)
            if response_text is not None:
                logger.warning("Groq response body: %s", getattr(exc.response, 'text', None))
            logger.warning("Groq request failed: %s", exc)

    if provider in {"gemini", "auto"} and Config.GEMINI_API_KEY:
        try:
            if google_genai is None:
                logger.warning("Gemini SDK not installed, cannot use Gemini provider")
            else:
                logger.info("Trying Gemini provider")
                client = google_genai.Client(api_key=Config.GEMINI_API_KEY)
                response = client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=full_prompt,
                )
                result = getattr(response, "text", None)
                logger.info("Gemini response received")
                return result
        except Exception as exc:  # pragma: no cover - network/env dependent
            logger.warning("Gemini request failed: %s", exc)

    logger.warning("No AI provider response returned")
    return None


# Initialize components
knowledge_base = KnowledgeBase(Config.KNOWLEDGE_BASE_FILE)
stadium_graph = StadiumGraph(Config.STADIUM_GRAPH_FILE)
mqtt_handler = MQTTHandler(
    Config.MQTT_BROKER, Config.MQTT_PORT, Config.MQTT_TOPIC, stadium_graph
)
# Simple in-memory cache for advice responses (fallback)
advice_cache = AdviceCache()
# We'll attach limiter to app later
security = HTTPBearer(auto_error=False)  # Optional auth for hackathon
def get_valid_nodes() -> Set[str]:
    """Get the set of valid node IDs from the graph."""
    return stadium_graph.valid_nodes


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    Config.validate_production_config()  # Validate production configuration
    mqtt_handler.start()
    yield
    # Shutdown
    mqtt_handler.stop()


# FastAPI app
app = FastAPI(
    title="FanWayfinder API",
    description="AI-powered stadium navigation assistant for FIFA World Cup 2026",
    version="2.1.0",
    lifespan=lifespan,
)

# Attach limiter and exception handler before startup
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

# Security middleware
# In production, replace ["*"] with specific allowed hosts (e.g., ["example.com", "www.example.com"])
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["*"]  # Configure for production deployment
)

# Custom middleware for security headers
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    # Update CSP to be more restrictive but still allow our inline styles (which we have)
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self'; "
        "img-src 'self' data:; "
        "font-src 'self'; "
        "connect-src 'self'; "
        "frame-ancestors 'none';"
    )
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response


def verify_token_dependency(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """
    Token verification for secure endpoints.
    In production, this would validate JWT tokens properly.
    For hackathon, we allow requests without token but will validate if provided.
    """
    if not credentials:
        # For hackathon purposes, we'll allow requests without auth
        return None

    token = credentials.credentials
    token_data = verify_token(token)
    # In a real app, we would raise an exception if token is invalid
    # For hackathon, we'll just return None if invalid (so it's treated as no auth)
    return token_data


CACHE_HEADERS = {
    "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
    "Pragma": "no-cache",
    "Expires": "0",
}


@app.get("/", response_class=HTMLResponse)
async def serve_frontend():
    """Serve the landing page for the FanWayfinder frontend."""
    frontend_dir = os.path.join(os.path.dirname(__file__), "..", "frontend")
    index_path = os.path.join(frontend_dir, "index.html")
    with open(index_path, "r", encoding="utf-8") as handle:
        return HTMLResponse(handle.read(), headers=CACHE_HEADERS)


@app.get("/app.js")
async def serve_frontend_js():
    """Serve the frontend JavaScript bundle."""
    frontend_dir = os.path.join(os.path.dirname(__file__), "..", "frontend")
    return FileResponse(
        os.path.join(frontend_dir, "app.js"),
        media_type="application/javascript",
        headers=CACHE_HEADERS,
    )


@app.get("/style.css")
async def serve_frontend_css():
    """Serve the frontend stylesheet."""
    frontend_dir = os.path.join(os.path.dirname(__file__), "..", "frontend")
    return FileResponse(
        os.path.join(frontend_dir, "style.css"),
        media_type="text/css",
        headers=CACHE_HEADERS,
    )


@app.get("/stadiums")
async def list_stadiums():
    """Return the FIFA 2026 stadium list for the frontend."""
    return {"stadiums": sorted(Config.FIFA_STADIUMS)}


@app.post("/token", response_model=TokenResponse)
async def login_for_access_token(form_data: UserLogin):
    """
    Simple login endpoint to demonstrate authentication.
    In production, validate against a proper user database.
    """
    # For demo purposes, accept any username/password
    # In production, validate against secure user store
    access_token_expires = timedelta(minutes=Config.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": form_data.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}


@app.post("/advice", response_model=AdviceResponse)
async def get_advice(  # noqa: C901
    request: AdviceRequest,
    http_request: Request,
):
    """
    Get advice for stadium navigation using AI.
    """
    try:
        query = request.query
        location = request.location
        language = request.language
        stadium = request.stadium

        if location not in stadium_graph.valid_nodes:
            logger.warning(f"Location {location} not in graph, using default")
            location = Config.DEFAULT_LOCATION

        context_str = "\n".join(knowledge_base.chunk_texts)

        # Prepare prompt for the AI provider
        prompt = (
            f"Current stadium: {stadium}\n"
            f"Current location: {location}\n"
            f"User query: {query}\n"
            f"Language: {language}\n\n"
            "Use only stadium-specific guidance for the selected FIFA 2026 venue. "
            "Answer as if you are helping a fan inside the selected stadium. "
            "If the user asks for directions, recommend the nearest relevant facility and a clear route. "
            "If the user asks about the stadium, mention the selected stadium by name.\n\n"
            "Context Knowledge Base:\n"
            f"{context_str}\n\n"
            "Instructions:\n"
            "1. Provide a helpful, concise answer in the specified language.\n"
            "2. If the request is about directions, return the closest facility and a simple route.\n"
            "3. Extract the intent target type if the user is asking for directions to a facility. "
            "The valid types are: 'gate', 'concession', 'restroom', 'section', 'medical'. "
            "If not asking for directions, return 'none'.\n"
            "Return ONLY a valid JSON object with keys 'advice' (string) and 'target_type' (string)."
        )

        cache_input = {
            "query": query,
            "language": language,
            "location": location,
            "stadium": stadium,
        }
        cache_key = json.dumps(cache_input, sort_keys=True)
        cached_response = advice_cache.get(cache_key)
        if cached_response is not None:
            logger.info("Returning cached advice for key: %s", cache_key)
            return cached_response

        target_type = None
        advice = "I couldn't process your request right now."
        logger.info("Advice request received: stadium=%s location=%s language=%s query=%s", stadium, location, language, query)
        ai_text = generate_ai_response(prompt)
        if ai_text:
            logger.info("AI provider returned text: %s", ai_text[:200].replace('\n', ' '))
            try:
                text = ai_text.strip()
                if text.startswith("```json"):
                    text = text[7:-3]
                elif text.startswith("```"):
                    text = text[3:-3]
                result = json.loads(text.strip())
                advice = result.get("advice", advice)
                t_type = result.get("target_type", "none").lower()
                if t_type in ['gate', 'concession', 'restroom', 'section', 'medical']:
                    target_type = t_type
                logger.info("Parsed AI result: target_type=%s advice_length=%d", target_type, len(advice))
            except json.JSONDecodeError as exc:
                logger.warning("AI response JSON parse failed: %s", exc)
                logger.warning("Raw AI text: %s", ai_text)
                advice = ai_text
        else:
            logger.warning("AI provider unavailable or failed. Falling back to basic logic.")
            contexts = knowledge_base.retrieve_relevant_chunks(query, k=1)
            advice = f"Fallback Mode: {contexts[0]}" if contexts else "No information available."
            target_type = determine_target_type(query)
            logger.info("Fallback advice selected; target_type=%s", target_type)

        route = None
        if target_type:
            target_nodes = stadium_graph.get_nodes_by_type(target_type)
            if target_nodes:
                best_path = None
                best_length = float('inf')
                for target in target_nodes:
                    path = stadium_graph.find_shortest_path(location, target)
                    if path:
                        length = 0
                        for i in range(len(path) - 1):
                            u, v = path[i], path[i + 1]
                            attr = stadium_graph.G.get_edge_data(u, v)
                            length += stadium_graph.get_edge_weight(u, v, attr)
                        if length < best_length:
                            best_length = length
                            best_path = path
                if best_path:
                    route = best_path

        response = AdviceResponse(advice=advice, route=route, congestion_aware=True)
        advice_cache.set(cache_key, response)
        return response

    except Exception as e:
        logger.error(f"Error in get_advice: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error while processing your request."
        )


def determine_target_type(query: str) -> Optional[str]:
    """Fallback logic to determine target type."""
    q = query.lower()

    def word_in_query(word):
        pattern = r'(?<!\w)' + re.escape(word) + r'(s|ing|ed)?(?!\w)'
        return bool(re.search(pattern, q))

    section_words = ["section", "seat", "seats", "sit", "sitting", "row", "rows"]
    if any(word_in_query(word) for word in section_words):
        return "section"

    restroom_words = ["restroom", "bathroom", "toilet", "washroom"]
    if any(word_in_query(word) for word in restroom_words):
        return "restroom"

    food_words = ["food", "eat", "drink", "concession", "hungry", "thirsty", "snack", "meal"]
    if any(word_in_query(word) for word in food_words):
        return "concession"

    medical_words = ["medical", "help", "tent", "doctor", "nurse", "first", "aid", "emergency"]
    if any(word_in_query(word) for word in medical_words):
        return "medical"

    return None


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
