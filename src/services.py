"""
FanWayfinder Services - Extracted from src/api.py
"""

import json
import logging
import os
import re
import threading
import time
from typing import Dict, List, Optional, Set, Tuple
from pathlib import Path

import networkx as nx
import paho.mqtt.client as mqtt
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from .config import Config

logger = logging.getLogger(__name__)


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
        self.cache: Dict[str, Tuple[float, 'AdviceResponse']] = {}
        self.lock = threading.RLock()

    def get(self, key: str) -> Optional['AdviceResponse']:
        with self.lock:
            if key in self.cache:
                timestamp, value = self.cache[key]
                if time.time() - timestamp < self.ttl:
                    return value
                else:
                    del self.cache[key]
        return None

    def set(self, key: str, value: 'AdviceResponse'):
        with self.lock:
            # Remove oldest if at capacity
            if len(self.cache) >= self.maxsize:
                # Simple FIFO removal (not truly LRU, but good enough for demo)
                oldest_key = next(iter(self.cache))
                del self.cache[oldest_key]
            self.cache[key] = (time.time(), value)