import json
import logging
import os
from typing import Dict, List, Optional, Any

from src.store import get_all_complaints, load_district_index, get_district_by_name

logger = logging.getLogger(__name__)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
AI_PROVIDER = os.getenv("AI_PROVIDER", "auto")


def _call_groq(prompt: str, model: str = "llama-3.1-8b-instant") -> Optional[str]:
    """Call Groq's OpenAI-compatible endpoint for chat completions."""
    import httpx

    if not GROQ_API_KEY:
        logger.warning("Groq API key not set, skipping Groq call")
        return None

    try:
        logger.info("Trying Groq provider with model %s", model)
        response = httpx.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": "You are CivicPulse, summarizing infrastructure complaints."},
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
        logger.warning("Groq request failed: %s", exc)
        return None


def _call_gemini(prompt: str, model: str = "gemini-1.5-flash") -> Optional[str]:
    """Call Google Gemini for content generation."""
    from google import genai

    if GEMINI_API_KEY is None:
        logger.warning("Gemini API key not set, skipping Gemini call")
        return None

    if google_genai is None:
        logger.warning("Gemini SDK not installed, cannot use Gemini provider")
        return None

    try:
        logger.info("Trying Gemini provider with model %s", model)
        client = google_genai.Client(api_key=GEMINI_API_KEY)
        gemini_response = client.models.generate_content(
            model=model,
            contents=prompt,
        )
        result = getattr(gemini_response, "text", None)
        logger.info("Gemini response received")
        return result
    except Exception as exc:  # pragma: no cover - network/env dependent
        logger.warning("Gemini request failed: %s", exc)
        return None


def _local_summary(complaints: List[Dict[str, Any]], districts: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Fallback local (non-LLM) summary: count complaints by district and category."""
    district_counts: Dict[str, int] = {}
    category_counts: Dict[str, int] = {}

    for c in complaints:
        cat = c.get("category", "unknown")
        loc = c.get("location", "unknown")
        category_counts[cat] = category_counts.get(cat, 0) + 1
        # Try to match location to a district
        districts_map = {d["district"]: d for d in districts}
        for dname, ddata in districts_map.items():
            if dname.lower() in loc.lower() or loc.lower() in dname.lower():
                district_counts[dname] = district_counts.get(dname, 0) + 1

    # Build ranked list: sort districts by complaint count desc, then by urgency
    ranked = sorted(
        district_counts.items(),
        key=lambda x: (x[1], district_counts.get(x[0], 0)),
        reverse=True,
    )

    return {
        "summary": f"Local summary: {len(complaints)} total complaints across {len(districts)} districts.",
        "ranked_districts": [
            {"district": d, "count": c} for d, c in ranked
        ],
        "category_breakdown": dict(category_counts),
    }


def summarize_and_rank() -> Dict[str, Any]:
    """Summarize all logged complaints and produce a ranked hotspot list by district.

    Fallback chain:
    1. Google Gemini (primary) - if GEMINI_API_KEY is set
    2. Groq (fallback) - if GROQ_API_KEY is set and Gemini fails or is missing
    3. Local non-LLM summary - if both fail or keys are missing
    """
    complaints = get_all_complaints()
    districts = load_district_index()

    if not complaints:
        return {
            "summary": "No complaints logged yet.",
            "ranked_districts": [],
            "category_breakdown": {},
        }

    # Build the prompt for the LLM
    complaint_summary_parts = []
    for c in complaints:
        part = f"- District: {c.get('location', 'unknown')}, Category: {c.get('category', 'unknown')}, "
        part += f"Urgency: {c.get('urgency', 'medium')}, Description: {c.get('description', '')[:80]}"
        complaint_summary_parts.append(part)

    prompt = f"""CivicPulse complaint summary and district hotspot ranking.

Logged complaints ({len(complaints)} total):
{''.join(complaint_summary_parts)}

Synthetic district infrastructure index (for scoring):
{json.dumps(load_district_index(), indent=2)}

Produce a ranked list of districts by complaint hotspot priority. For each district, provide:
- district name
- number of complaints
- inferred urgency level (high/medium/low)
- recommended action priority

Also provide a one-paragraph summary of the overall complaint landscape.

Return valid JSON with three fields:
- "summary": one-paragraph summary string
- "ranked_districts": list of district objects (each with name, count, urgency, action_priority)
- "category_breakdown": mapping of category -> count
"""

    # Attempt 1: Google Gemini
    if AI_PROVIDER in {"gemini", "auto"} and GEMINI_API_KEY:
        gemini_result = _call_gemini(prompt, model="gemini-1.5-flash")
        if gemini_result:
            try:
                parsed = json.loads(gemini_result)
                if isinstance(parsed, dict) and "summary" in parsed:
                    logger.info("Gemini summarization succeeded")
                    return parsed
            except (json.JSONDecodeError, TypeError) as exc:
                logger.warning("Gemini response was not valid JSON: %s", exc)

    # Attempt 2: Groq
    if AI_PROVIDER in {"groq", "auto"} and GROQ_API_KEY:
        groq_result = _call_groq(prompt, model="llama-3.1-8b-instant")
        if groq_result:
            try:
                parsed = json.loads(groq_result)
                if isinstance(parsed, dict) and "summary" in parsed:
                    logger.info("Groq summarization succeeded")
                    return parsed
            except (json.JSONDecodeError, TypeError) as exc:
                logger.warning("Groq response was not valid JSON: %s", exc)

    # Attempt 3: Local non-LLM summary
    logger.info("Falling back to local non-LLM summary")
    return _local_summary(complaints, districts)