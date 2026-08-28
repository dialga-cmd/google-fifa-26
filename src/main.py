"""CivicPulse analytics service — FastAPI app that reads logged complaints
and produces a ranked hotspot list by district.

Endpoints:
- GET /hotspots - Returns the ranked complaint hotspot list
- GET /complaints - Returns all logged complaints
- POST /complaints - Log a new complaint
"""

import logging
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from typing import Any, List, Optional

from src.store import get_all_complaints, insert_complaint, load_district_index
from src.summarize import summarize_and_rank

app = FastAPI(
    title="CivicPulse Analytics",
    description="Analytics service for citizen infrastructure complaint intake system",
    version="1.0.0",
)

logger = logging.getLogger(__name__)


@app.get("/hotspots", response_model=dict)
async def get_hotspots() -> dict:
    """Return the ranked complaint hotspot list."""
    try:
        result = summarize_and_rank()
        return JSONResponse(content=result)
    except Exception as exc:
        logger.error("Failed to generate hotspot list: %s", exc)
        raise HTTPException(status_code=500, detail="Internal server error while generating hotspot list")


@app.get("/complaints", response_model=List[dict])
async def get_complaints() -> List[dict]:
    """Return all logged complaints."""
    return get_all_complaints()


@app.post("/complaints", response_model=dict)
async def log_complaint(
    category: str,
    location: str,
    description: Optional[str] = None,
    urgency: str = "medium",
    citizen_name: Optional[str] = None,
    contact: Optional[str] = None,
) -> dict:
    """Log a new infrastructure complaint and return the recorded record."""
    try:
        rowid = insert_complaint(
            category=category,
            location=location,
            description=description,
            urgency=urgency,
            citizen_name=citizen_name,
            contact=contact,
        )
        return {"id": rowid, "category": category, "location": location, "urgency": urgency, "status": "logged"}
    except Exception as exc:
        logger.error("Failed to log complaint: %s", exc)
        raise HTTPException(status_code=500, detail="Internal server error while logging complaint")