import csv
import json
import os
import sqlite3
from typing import Dict, List, Optional, Any

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    # Project structure: data/ at root, backend/data/ for synthetic datasets
    DATA_DIR = os.path.join(BASE_DIR, "backend", "data")


def get_db_path() -> str:
    return os.path.join(BASE_DIR, "data", "complaints.db")


def init_db() -> sqlite3.Connection:
    """Initialize the SQLite database and return a connection."""
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS complaints ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "category TEXT NOT NULL, "
        "location TEXT NOT NULL, "
        "description TEXT, "
        "urgency TEXT NOT NULL DEFAULT 'medium', "
        "citizen_name TEXT, "
        "contact TEXT, "
        "created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"
    )
    conn.commit()
    return conn


def insert_complaint(
    category: str,
    location: str,
    description: Optional[str],
    urgency: str,
    citizen_name: Optional[str] = None,
    contact: Optional[str] = None,
) -> int:
    """Insert a new complaint into the database and return its rowid."""
    conn = init_db()
    cur = conn.execute(
        "INSERT INTO complaints (category, location, description, urgency, citizen_name, contact) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (category, location, description, urgency, citizen_name, contact),
    )
    conn.commit()
    last_id = cur.lastrowid
    conn.close()
    return last_id


def get_all_complaints() -> List[Dict[str, Any]]:
    """Retrieve all complaints from the database, ordered by creation date descending."""
    conn = init_db()
    cur = conn.execute(
        "SELECT id, category, location, description, urgency, citizen_name, contact, created_at FROM complaints ORDER BY created_at DESC"
    )
    rows = cur.fetchall()
    conn.close()
    return [
        {
            "id": row[0],
            "category": row[1],
            "location": row[2],
            "description": row[3],
            "urgency": row[4],
            "citizen_name": row[5],
            "contact": row[6],
            "created_at": row[7],
        }
        for row in rows
    ]


def get_complaints_by_category(category: str) -> List[Dict[str, Any]]:
    """Retrieve complaints filtered by category."""
    conn = init_db()
    cur = conn.execute(
        "SELECT id, category, location, description, urgency, citizen_name, contact, created_at FROM complaints WHERE category = ? ORDER BY created_at DESC",
        (category,),
    )
    rows = cur.fetchall()
    conn.close()
    return [
        {
            "id": row[0],
            "category": row[1],
            "location": row[2],
            "description": row[3],
            "urgency": row[4],
            "citizen_name": row[5],
            "contact": row[6],
            "created_at": row[7],
        }
        for row in rows
    ]


def load_district_index() -> List[Dict[str, Any]]:
    """Load the synthetic district infrastructure index from CSV."""
    path = os.path.join(DATA_DIR, "district_infra_index.csv")
    rows = []
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            row["urgency_score"] = int(row.get("urgency_score", 0) or 0)
            row["population_served"] = int(row.get("population_served", 0) or 0)
            row["complaint_count"] = int(row.get("complaint_count", 0) or 0)
            row["last_reported"] = row.get("last_reported", "")
            rows.append(row)
    return rows


def get_district_by_name(district_name: str) -> Optional[Dict[str, Any]]:
    """Get a single district entry by name from the index."""
    index = load_district_index()
    for district in index:
        if district["district"] == district_name:
            return district
    return None