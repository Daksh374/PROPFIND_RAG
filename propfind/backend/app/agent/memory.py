"""
memory.py — User memory CRUD and automatic preference extraction.
"""
from __future__ import annotations

import logging
import re
from datetime import datetime

from sqlalchemy.orm import Session

from app.database import UserMemory, SessionLocal

logger = logging.getLogger(__name__)

# Keys tracked in memory
MEMORY_KEYS = {
    "budget",
    "preferred_locality",
    "bhk_preference",
    "must_have_amenities",
    "listing_type_preference",
    "user_name",
    "user_email",
}


def get_user_memory(user_identifier: str) -> dict[str, str]:
    """Return all memory entries for a user as a flat dict."""
    with SessionLocal() as session:
        rows = (
            session.query(UserMemory)
            .filter(UserMemory.user_identifier == user_identifier)
            .all()
        )
        return {row.key: row.value for row in rows}


def update_user_memory(user_identifier: str, key: str, value: str) -> None:
    """Upsert a single memory key for a user."""
    with SessionLocal() as session:
        existing = (
            session.query(UserMemory)
            .filter(
                UserMemory.user_identifier == user_identifier,
                UserMemory.key == key,
            )
            .first()
        )
        if existing:
            existing.value = value
            existing.updated_at = datetime.utcnow()
        else:
            session.add(
                UserMemory(
                    user_identifier=user_identifier,
                    key=key,
                    value=value,
                )
            )
        session.commit()
    logger.info(f"Memory updated for {user_identifier}: {key}={value}")


def bulk_update_memory(user_identifier: str, updates: dict[str, str]) -> None:
    for k, v in updates.items():
        if k in MEMORY_KEYS and v:
            update_user_memory(user_identifier, k, str(v))


def extract_and_store_memory(user_identifier: str, user_message: str) -> None:
    """
    Heuristically extract preferences from the user's message and persist them.
    This is a lightweight rule-based extractor — no LLM call needed.
    """
    updates: dict[str, str] = {}

    # Budget extraction: "budget 50 lakhs", "under 1 crore", "₹25000/month"
    budget_match = re.search(
        r"(?:budget|under|within|max(?:imum)?)\s+(?:₹|rs\.?|inr)?\s*([\d,]+)\s*(lakh|l|cr|crore|k)?",
        user_message,
        re.IGNORECASE,
    )
    if budget_match:
        amount = float(budget_match.group(1).replace(",", ""))
        unit = (budget_match.group(2) or "").lower()
        if unit in ("lakh", "l"):
            amount *= 100_000
        elif unit in ("crore", "cr"):
            amount *= 10_000_000
        elif unit == "k":
            amount *= 1_000
        updates["budget"] = str(int(amount))

    # BHK preference
    bhk_match = re.search(r"(\d)\s*bhk", user_message, re.IGNORECASE)
    if bhk_match:
        updates["bhk_preference"] = bhk_match.group(1)

    # Locality hints
    localities = [
        "Noida", "Gurgaon", "Gurugram", "Dwarka", "Rohini", "Vasant Kunj",
        "Greater Noida", "Faridabad", "Ghaziabad", "Lajpat Nagar", "Hauz Khas",
        "Saket", "Malviya Nagar", "Janakpuri", "Pitampura", "Shalimar Bagh",
        "Cyber City", "DLF", "Indirapuram", "Vaishali",
    ]
    for loc in localities:
        if loc.lower() in user_message.lower():
            updates["preferred_locality"] = loc
            break

    # Listing type
    if re.search(r"\brent\b|\brenting\b", user_message, re.IGNORECASE):
        updates["listing_type_preference"] = "RENT"
    elif re.search(r"\bbuy\b|\bpurchase\b|\bsale\b|\bbuying\b", user_message, re.IGNORECASE):
        updates["listing_type_preference"] = "SALE"
    elif re.search(r"\bpg\b|\bpaying guest\b", user_message, re.IGNORECASE):
        updates["listing_type_preference"] = "PG"

    if updates:
        bulk_update_memory(user_identifier, updates)
        logger.info(f"Auto-extracted preferences for {user_identifier}: {updates}")
