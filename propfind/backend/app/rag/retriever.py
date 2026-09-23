"""
retriever.py — Hybrid retrieval: Conversation Context Reformulation → SQL Filtering → ChromaDB Vector Search.
"""
from __future__ import annotations

import logging
import json
import re
from typing import Any

from sqlalchemy import and_
from sqlalchemy.orm import Session

from app.config import get_groq_client, GROQ_FAST_MODEL
from app.database import Property, PropertyAmenity, SessionLocal
from app.ingest.embedder import query_collection

logger = logging.getLogger(__name__)

# ─── Query Reformulation via fast LLM ──────────────────────────────────────────

_REFORMULATE_SYSTEM = """You are a real estate search query reformulation assistant.
Given a chat conversation history and a follow-up user query, rewrite the query into a complete, standalone search query.
If the user query asks for details, owner info, contact info, price, or visits for an item by index/number (e.g. '1', '#1', 'first property', 'property 1', 'owner of 1', 'it', 'this one'), replace the reference with the explicit Property ID (e.g. PROP1001) or full property title mentioned in the previous assistant message.
For example, if history contains '1. [PROP1001] 2 BHK Apartment in Gurgaon Sector 56' and user asks 'Give owner details of 1', rewrite to: 'owner details for property PROP1001'.
Return ONLY the reformulated query text string, without markdown formatting or quotes."""


def reformulate_query(query: str, chat_history: list[dict] | None = None) -> str:
    """Rewrite follow-up queries like 'Where is it?' into standalone search queries."""
    if not chat_history:
        return query
    try:
        client = get_groq_client()
        messages = [{"role": "system", "content": _REFORMULATE_SYSTEM}]
        for m in chat_history[-6:]:
            role = m.get("role", "user")
            content = m.get("content", "")
            if role in ("user", "assistant") and content:
                messages.append({"role": role, "content": content})
        messages.append({"role": "user", "content": f"Follow-up question: {query}"})

        resp = client.chat.completions.create(
            model=GROQ_FAST_MODEL,
            messages=messages,
            temperature=0,
            max_tokens=100,
            reasoning_effort="low",
        )
        reformulated = resp.choices[0].message.content.strip()
        if reformulated and len(reformulated) > 2:
            logger.info(f"Query reformulated: '{query}' -> '{reformulated}'")
            return reformulated
    except Exception as e:
        logger.warning(f"Query reformulation failed: {e}")
    return query


# ─── Filter extraction via fast LLM call ─────────────────────────────────────

_FILTER_SYSTEM = """You are a JSON filter extractor for a Delhi NCR real estate search engine.
Extract structured query parameters from the user's input.

CRITICAL PRICE EXTRACTION RULES:
- "under", "below", "less than", "budget", "up to", "within", "max" X => set max_price: X (do NOT set min_price!)
- "above", "more than", "starting from", "at least", "min" X => set min_price: X (do NOT set max_price!)
- "between X and Y" => set min_price: X, max_price: Y

CRITICAL PG & FOOD RULES:
- "food", "food included", "with food", "meals", "mess" => set food_included: true (do NOT put "food" or "food included" in amenities!)
- "without food", "food not included", "no food" => set food_included: false
- "veg" / "vegetarian" => set food_type: "VEG"
- "non-veg" / "non vegetarian" => set food_type: "NON_VEG"
- "boys", "male", "gents" => set gender_preference: "MALE"
- "girls", "female", "ladies" => set gender_preference: "FEMALE"
- "unisex", "co-ed", "both" => set gender_preference: "UNISEX"
- "single", "private room" => set occupancy_type: "SINGLE"
- "double", "twin" => set occupancy_type: "DOUBLE_SHARING"
- "triple" => set occupancy_type: "TRIPLE_SHARING"

Return ONLY a valid JSON object with these keys (omit keys if not specified in query):
{
  "property_id": "string (e.g. PROP1001) or null",
  "locality": "Delhi NCR area/city/locality name (e.g. Noida, Gurgaon, Dwarka) or null (do NOT extract person or owner names)",
  "bhk": int or null,
  "min_price": float or null,
  "max_price": float or null,
  "listing_type": "RENT" | "SALE" | "PG" | null,
  "property_type": "APARTMENT" | "BUILDER_FLOOR" | "INDEPENDENT_HOUSE" | "PG" | null,
  "near_metro": true | false | null,
  "food_included": true | false | null,
  "food_type": "VEG" | "NON_VEG" | "BOTH" | null,
  "occupancy_type": "SINGLE" | "DOUBLE_SHARING" | "TRIPLE_SHARING" | null,
  "gender_preference": "MALE" | "FEMALE" | "UNISEX" | "ANY" | null,
  "amenities": ["amenity names mentioned by the user (excluding food/meals)"] | null
}
Output ONLY raw valid JSON."""

_LOCALITY_ALIASES = {
    "gurugram": "Gurgaon",
    "gurgaon": "Gurgaon",
    "greater noida": "Greater Noida",
}

_KNOWN_LOCALITIES = [
    "Greater Noida", "Vasant Kunj", "Lajpat Nagar", "Malviya Nagar",
    "Shalimar Bagh", "Cyber City", "Indirapuram", "Janakpuri",
    "Pitampura", "Faridabad", "Ghaziabad", "Dwarka", "Rohini",
    "Hauz Khas", "Saket", "Vaishali", "Noida", "Gurgaon", "Gurugram",
]

_PROPERTY_TYPE_PATTERNS = [
    (r"\bbuilder\s*floor\b", "BUILDER_FLOOR"),
    (r"\bindependent\s*(?:house|home)\b", "INDEPENDENT_HOUSE"),
    (r"\bapartments?\b|\bflats?\b", "APARTMENT"),
    (r"\bpg\b|\bpaying\s+guest\b", "PG"),
]

_AMENITY_TERMS = [
    "gym", "swimming pool", "pool", "parking", "lift", "security",
    "power backup", "clubhouse", "garden", "balcony", "furnished",
    "wifi", "ac", "air conditioning",
]

_REAL_ESTATE_TERMS = {
    "property", "properties", "listing", "listings", "rent", "rental",
    "sale", "buy", "purchase", "apartment", "flat", "house", "home",
    "builder floor", "pg", "paying guest", "bhk", "locality", "metro",
    "amenity", "amenities", "budget", "price", "owner", "visit",
    "inquiry", "compare", "sqft", "room", "accommodation", "food",
}


def _parse_amount(raw_amount: str, raw_unit: str | None) -> float:
    amount = float(raw_amount.replace(",", ""))
    unit = (raw_unit or "").lower()
    if unit in {"lakh", "lakhs", "lac", "lacs", "l"}:
        amount *= 100_000
    elif unit in {"crore", "crores", "cr"}:
        amount *= 10_000_000
    elif unit in {"k", "thousand"}:
        amount *= 1_000
    return amount


def _merge_filters(primary: dict[str, Any], fallback: dict[str, Any]) -> dict[str, Any]:
    merged = {k: v for k, v in primary.items() if v not in (None, "", [])}
    for key, value in fallback.items():
        if key == "amenities":
            current = merged.get("amenities") or []
            merged[key] = sorted({*current, *value})
        elif key not in merged or merged[key] in (None, "", []):
            merged[key] = value
    return merged


def _rule_based_filters(query: str) -> dict[str, Any]:
    """Extract common real-estate filters without depending on an LLM."""
    q = query.lower()
    filters: dict[str, Any] = {}

    prop_match = re.search(r"\bprop\s*[-_ ]?(\d{3,})\b", q, re.IGNORECASE)
    if prop_match:
        filters["property_id"] = f"PROP{prop_match.group(1)}"
    else:
        prop_match = re.search(r"\bPROP\d{3,}\b", query, re.IGNORECASE)
        if prop_match:
            filters["property_id"] = prop_match.group(0).upper()

    for loc in _KNOWN_LOCALITIES:
        if re.search(rf"\b{re.escape(loc.lower())}\b", q):
            filters["locality"] = _LOCALITY_ALIASES.get(loc.lower(), loc)
            break

    bhk_match = re.search(r"\b([1-9])\s*bhk\b", q)
    if bhk_match:
        filters["bhk"] = int(bhk_match.group(1))

    if re.search(r"\bpg\b|\bpaying\s+guest\b", q):
        filters["listing_type"] = "PG"
        filters["property_type"] = "PG"
    elif re.search(r"\brent(?:al|ing)?\b|\b/month\b|\bper\s+month\b", q):
        filters["listing_type"] = "RENT"
    elif re.search(r"\bbuy(?:ing)?\b|\bpurchase\b|\bsale\b|\bfor\s+sale\b", q):
        filters["listing_type"] = "SALE"

    for pattern, value in _PROPERTY_TYPE_PATTERNS:
        if re.search(pattern, q):
            filters["property_type"] = value
            break

    if re.search(r"\bnear\s+(?:a\s+)?metro\b|\bmetro\s+(?:station|connectivity)\b", q):
        filters["near_metro"] = True

    if re.search(r"\b(?:with\s+)?food(?:\s+included)?\b|\bmeals?(?:\s+included)?\b|\bmess\b", q):
        if not re.search(r"\bwithout\s+food\b|\bno\s+food\b", q):
            filters["food_included"] = True
    elif re.search(r"\bwithout\s+food\b|\bno\s+food\b", q):
        filters["food_included"] = False

    if re.search(r"\bnon[- ]?veg(?:etarian)?\b", q):
        filters["food_type"] = "NON_VEG"
    elif re.search(r"\bveg(?:etarian)?\b", q):
        filters["food_type"] = "VEG"

    if re.search(r"\bgirls?\b|\bfemale\b|\bladies\b", q):
        filters["gender_preference"] = "FEMALE"
    elif re.search(r"\bboys?\b|\bmale\b|\bgents\b", q):
        filters["gender_preference"] = "MALE"
    elif re.search(r"\bunisex\b|\bco-?ed\b", q):
        filters["gender_preference"] = "UNISEX"

    if re.search(r"\bsingle(?:\s+occupancy|\s+room)?\b", q):
        filters["occupancy_type"] = "SINGLE"
    elif re.search(r"\bdouble(?:\s+sharing|\s+occupancy|\s+room)?\b|\btwin\b", q):
        filters["occupancy_type"] = "DOUBLE_SHARING"
    elif re.search(r"\btriple(?:\s+sharing|\s+occupancy|\s+room)?\b", q):
        filters["occupancy_type"] = "TRIPLE_SHARING"

    money = r"(?:₹|rs\.?|inr)?\s*([\d,]+(?:\.\d+)?)\s*(crores?|cr|lakhs?|lacs?|l|k|thousand)?"
    between_match = re.search(rf"\bbetween\s+{money}\s+(?:and|to|-)\s+{money}", q)
    if between_match:
        filters["min_price"] = _parse_amount(between_match.group(1), between_match.group(2))
        filters["max_price"] = _parse_amount(between_match.group(3), between_match.group(4))
    else:
        max_match = re.search(rf"\b(?:under|below|less\s+than|budget|up\s+to|within|max(?:imum)?)\s+{money}", q)
        min_match = re.search(rf"\b(?:above|over|more\s+than|starting\s+from|at\s+least|min(?:imum)?)\s+{money}", q)
        if max_match:
            filters["max_price"] = _parse_amount(max_match.group(1), max_match.group(2))
        if min_match:
            filters["min_price"] = _parse_amount(min_match.group(1), min_match.group(2))

    amenities = []
    for term in _AMENITY_TERMS:
        if re.search(rf"\b{re.escape(term)}\b", q):
            amenities.append("swimming pool" if term == "pool" else term)
    if amenities:
        filters["amenities"] = sorted(set(amenities))

    return filters


def extract_filters(query: str) -> dict[str, Any]:
    """Extract structured filters, using deterministic parsing as a safety net."""
    fallback = _rule_based_filters(query)
    try:
        client = get_groq_client()
        resp = client.chat.completions.create(
            model=GROQ_FAST_MODEL,
            messages=[
                {"role": "system", "content": _FILTER_SYSTEM},
                {"role": "user", "content": query},
            ],
            temperature=0,
            max_tokens=200,
            reasoning_effort="low",
        )
        raw = resp.choices[0].message.content.strip()
        raw = re.sub(r"```(?:json)?", "", raw).strip().rstrip("```").strip()
        filters = json.loads(raw)
        merged = _merge_filters(
            {k: v for k, v in filters.items() if v is not None},
            fallback,
        )
    except Exception as e:
        logger.warning(f"Filter extraction failed: {e}")
        merged = fallback

    # Clean up amenities to ensure "food" terms do not stay in amenities array
    amenities = merged.get("amenities") or []
    cleaned_amenities = []
    for a in amenities:
        a_lower = str(a).lower()
        if any(term in a_lower for term in ["food", "meal", "mess"]):
            if "food_included" not in merged:
                merged["food_included"] = False if ("without" in a_lower or "no " in a_lower) else True
        else:
            cleaned_amenities.append(a)

    if cleaned_amenities:
        merged["amenities"] = cleaned_amenities
    elif "amenities" in merged:
        del merged["amenities"]

    return merged


def is_real_estate_query(query: str, filters: dict[str, Any]) -> bool:
    """Avoid retrieving arbitrary listings for clearly unrelated questions."""
    if filters:
        return True
    q = query.lower()
    return any(term in q for term in _REAL_ESTATE_TERMS)


# ─── SQL pre-filter ───────────────────────────────────────────────────────────

def sql_filter_property_ids(session: Session, filters: dict) -> list[str] | None:
    """
    Apply structured filters to get a candidate property_id set.
    Returns None if no filters → no pre-filtering (search all).
    """
    # High-priority exact match if property_id is present
    if filters.get("property_id"):
        pid = str(filters["property_id"]).upper().strip()
        exists = session.query(Property.property_id).filter(Property.property_id == pid).first()
        if exists:
            return [pid]

    clauses = []

    if filters.get("locality"):
        loc = filters["locality"]
        clauses.append(Property.locality.ilike(f"%{loc}%"))

    if filters.get("bhk") is not None:
        clauses.append(Property.bhk == int(filters["bhk"]))

    if filters.get("min_price") is not None:
        clauses.append(Property.price >= float(filters["min_price"]))

    if filters.get("max_price") is not None:
        clauses.append(Property.price <= float(filters["max_price"]))

    if filters.get("listing_type"):
        clauses.append(Property.listing_type == filters["listing_type"].upper())

    if filters.get("property_type"):
        clauses.append(Property.property_type == filters["property_type"].upper())

    if filters.get("near_metro") is True:
        clauses.append(Property.near_metro.is_(True))

    if filters.get("food_included") is True:
        clauses.append(Property.food_included.is_(True))
    elif filters.get("food_included") is False:
        clauses.append(Property.food_included.is_(False))

    if filters.get("food_type"):
        ft = str(filters["food_type"]).upper()
        clauses.append(Property.food_type.ilike(f"%{ft}%"))

    if filters.get("gender_preference"):
        gp = str(filters["gender_preference"]).upper()
        clauses.append(Property.gender_preference.ilike(f"%{gp}%"))

    if filters.get("occupancy_type"):
        occ = str(filters["occupancy_type"]).upper()
        clauses.append(Property.occupancy_type.ilike(f"%{occ}%"))

    for amenity in filters.get("amenities") or []:
        clauses.append(
            Property.amenities.any(PropertyAmenity.amenity_name.ilike(f"%{amenity}%"))
        )

    if not clauses:
        return None

    q = session.query(Property.property_id)
    q = q.filter(and_(*clauses))
    ids = [row.property_id for row in q.limit(500).all()]
    return ids


# ─── Main retrieval function ──────────────────────────────────────────────────

def retrieve(
    query: str,
    n_results: int = 8,
    filters: dict | None = None,
    chat_history: list[dict] | None = None,
) -> list[dict]:
    """
    Full hybrid retrieval pipeline:
      1. Reformulate query using conversation context if available
      2. Extract filters (or use provided)
      3. SQL pre-filter → candidate property_ids
      4. Vector search in ChromaDB restricted to those IDs
      5. Return enriched result dicts
    """
    search_query = reformulate_query(query, chat_history) if chat_history else query

    with SessionLocal() as session:
        effective_filters = filters if filters is not None else extract_filters(search_query)
        if not is_real_estate_query(search_query, effective_filters):
            logger.info("Skipping retrieval for out-of-domain query: %s", search_query)
            return []

        candidate_ids = sql_filter_property_ids(session, effective_filters)

        if candidate_ids is not None and len(candidate_ids) == 0:
            logger.info("Candidate pre-filter returned 0 results.")
            return []

        logger.info(f"Search Query: '{search_query}' | Filters: {effective_filters} | Candidates: {len(candidate_ids) if candidate_ids is not None else 'all'}")

        # Build ChromaDB where clause
        chroma_where = None
        if candidate_ids is not None:
            if len(candidate_ids) == 1:
                chroma_where = {"property_id": {"$eq": candidate_ids[0]}}
            else:
                chroma_where = {"property_id": {"$in": candidate_ids}}

        results = query_collection(
            query_text=search_query,
            n_results=min(n_results, max(len(candidate_ids), 1) if candidate_ids else n_results),
            where=chroma_where,
        )

        docs = results.get("documents", [[]])[0]
        metas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]

        enriched = []
        for doc, meta, dist in zip(docs, metas, distances):
            item = {
                "text": doc,
                "score": round(1 - dist, 4),
                **meta,
            }
            enriched.append(item)

        return enriched
