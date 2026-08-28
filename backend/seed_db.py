"""Seed script that inserts 15-20 realistic fake complaints into the SQLite database.

Run: python3 backend/seed_db.py
"""

import random
import string

from src.store import insert_complaint


def random_string(length):
    """Generate a random string of fixed length."""
    return "".join(random.choices(string.ascii_letters + string.digits, k=length))


CATEGORIES = ["road", "water", "electricity", "sanitation"]


LOCATIONS_BY_CATEGORY = {
    "road": [
        "Main Street & 5th Ave",
        "Highway 101 off-ramp",
        "Downtown intersection",
        "Bridge near River Road",
        "Residential cul-de-sac",
    ],
    "water": [
        "Lakeview Reservoir",
        "Old Town water main",
        "City Park irrigation",
        "Riverwalk pipeline",
        "University campus lines",
    ],
    "electricity": [
        "Downtown substation",
        "Northeast feeder line",
        "Industrial park feeder",
        "Rural transformer",
        "Apartment complex panel",
    ],
    "sanitation": [
        "Central waste facility",
        "Street dumpster overflow",
        "Sewer cleanout",
        "Recycling pickup zone",
        "Public restroom",
    ],
}


URGENCY_LEVELS = ["low", "medium", "high"]
URGENCY_WEIGHTS = [0.5, 0.35, 0.15]


def random_urgency():
    """Return a weighted random urgency level."""
    return random.choices(URGENCY_LEVELS, weights=URGENCY_WEIGHTS)[0]


def random_citizen_name():
    """Generate a simple deterministic citizen name."""
    return "Citizen-" + random_string(6)


def random_contact():
    """Generate a random phone number 1/3 of the time, None otherwise."""
    if random.random() > 0.3:
        return "+1-555-" + random_string(4) + "-" + random_string(4)
    return None


for i in range(1, 21):
    category = random.choice(CATEGORIES)
    location = random.choice(LOCATIONS_BY_CATEGORY[category])
    description_templates = {
        "road": [
            "Pothole reported causing vehicle damage",
            "Road flooding after rainstorm",
            "Sinkhole appearing on road surface",
            "Street sign damaged, blocking lane",
            "Asphalt crumbling at intersection",
        ],
        "water": [
            "Water main break flooding basement",
            "Low water pressure in neighborhood",
            "Discolored water coming from taps",
            "Water leak on public street",
            "Reservoir level dropping rapidly",
        ],
        "electricity": [
            "Power outage affecting entire block",
            "Transformer sparking and smoking",
            "Frequent brownouts in evenings",
            "Downed power line on street",
            "Meter reading incorrectly high",
        ],
        "sanitation": [
            "Dumpster overflow attracting pests",
            "Sewage smell in public area",
            "Recycling not collected for 2 weeks",
            "Public restroom out of supplies",
            "Illegal dumping near park",
        ],
    }
    description = random.choice(description_templates[category])
    urgency = random_urgency()
    citizen_name = random_citizen_name()
    contact = random_contact()

    insert_complaint(
        category=category,
        location=location,
        description=description,
        urgency=urgency,
        citizen_name=citizen_name,
        contact=contact,
    )

    print("Seed {}/20: Inserted complaint - {} at {} (urgency: {})".format(i, category, location, urgency))

print("Successfully seeded 20 realistic fake complaints into the database.")
