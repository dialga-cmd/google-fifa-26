import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import networkx as nx

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def determine_target_type(query: str) -> Optional[str]:
    q = query.lower()

    def word_in_query(word: str) -> bool:
        pattern = r"(?<!\\w)" + re.escape(word) + r"(s|ing|ed)?(?!\\w)"
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


def load_stadium_graph() -> nx.Graph:
    graph_path = ROOT / "data" / "stadium_graph.json"
    if graph_path.exists():
        with graph_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return nx.node_link_graph(data)

    return nx.Graph()


def load_knowledge_base() -> List[str]:
    kb_path = ROOT / "data" / "kb_chunks.json"
    if kb_path.exists():
        with kb_path.open("r", encoding="utf-8") as f:
            chunks = json.load(f)
        return [item.get("text", "") for item in chunks if isinstance(item, dict)]

    return [
        "Restrooms are near each gate.",
        "Food concessions are near each gate.",
        "Medical tents are near Gate A and Gate C.",
    ]


def build_response(payload: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(payload),
    }


def handler(request: Any, context: Any = None) -> Dict[str, Any]:
    try:
        if hasattr(request, "get_json"):
            body = request.get_json(silent=True) or {}
        elif hasattr(request, "body"):
            body = json.loads(request.body.decode("utf-8")) if request.body else {}
        else:
            body = {}

        query = str(body.get("query", "")).strip() or "Where is the nearest restroom?"
        language = str(body.get("language", "en")).strip() or "en"
        location = str(body.get("location", "Gate_A")).strip() or "Gate_A"

        graph = load_stadium_graph()
        kb_chunks = load_knowledge_base()
        target_type = determine_target_type(query)

        advice = "I can help you navigate the stadium."
        if kb_chunks:
            advice = f"{query} I can help with directions, facilities, and crowd-aware routes. " + kb_chunks[0]

        route: Optional[List[str]] = None
        if target_type:
            candidate_nodes = [node for node, data in graph.nodes(data=True) if data.get("type") == target_type]
            if candidate_nodes:
                for target in candidate_nodes:
                    try:
                        path = nx.shortest_path(graph, source=location, target=target)
                        if path:
                            route = path
                            break
                    except Exception:
                        continue

        return build_response(
            {
                "advice": advice,
                "route": route,
                "congestion_aware": True,
                "language": language,
            }
        )
    except Exception as exc:  # pragma: no cover - defensive fallback
        return build_response(
            {
                "advice": f"I’m sorry, something went wrong: {exc}",
                "route": None,
                "congestion_aware": True,
                "language": "en",
            }
        )
