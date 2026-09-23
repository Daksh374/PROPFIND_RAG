"""
tools.py — All 7 LangGraph-compatible tools with full Pydantic schemas.
"""
from __future__ import annotations

import json
import logging
import statistics
from datetime import datetime
from typing import Optional

from langchain_core.tools import tool
from pydantic import BaseModel, Field
from sqlalchemy import and_, func

from app.database import (
    Property, PropertyAmenity, Owner, PastSale,
    TenantHistory, Visit, Inquiry, SessionLocal
)
from app.rag.retriever import retrieve

import re

logger = logging.getLogger(__name__)


def resolve_property_id(property_id_input: str, session) -> Property | None:
    """Helper to resolve property IDs from inputs like 'PROP1001', '1', 'prop 1001', or titles."""
    pid = (str(property_id_input) if property_id_input is not None else "").strip()
    if not pid:
        return None

    # 1. Exact match on property_id (case-insensitive)
    prop = session.query(Property).filter(Property.property_id.ilike(pid)).first()
    if prop:
        return prop

    # 2. Extract PROP... pattern e.g. "PROP 1001", "prop-1001"
    prop_match = re.search(r"\bPROP\s*[-_ ]?(\d+)\b", pid, re.IGNORECASE)
    if prop_match:
        formatted = f"PROP{prop_match.group(1)}"
        prop = session.query(Property).filter(Property.property_id == formatted).first()
        if prop:
            return prop

    # 3. Numeric index or ID e.g. "1" or "1001"
    if pid.isdigit():
        num = int(pid)
        formatted = f"PROP{num}"
        prop = session.query(Property).filter(Property.property_id == formatted).first()
        if prop:
            return prop

        if 1 <= num <= 50:
            props = session.query(Property).order_by(Property.property_id).all()
            if num <= len(props):
                return props[num - 1]

    # 4. Substring match on title
    prop = session.query(Property).filter(Property.title.ilike(f"%{pid}%")).first()
    if prop:
        return prop

    return None


# ─── Tool 1: search_properties ───────────────────────────────────────────────

class SearchInput(BaseModel):
    query: str = Field(..., description="Natural language search query")
    locality: Optional[str] = Field(None, description="Locality/area filter")
    bhk: Optional[int] = Field(None, description="Number of bedrooms (BHK)")
    min_price: Optional[float] = Field(None, description="Minimum price in ₹")
    max_price: Optional[float] = Field(None, description="Maximum price in ₹")
    listing_type: Optional[str] = Field(None, description="RENT, SALE, or PG")
    property_type: Optional[str] = Field(None, description="APARTMENT, BUILDER_FLOOR, INDEPENDENT_HOUSE, PG")
    near_metro: Optional[bool] = Field(None, description="Filter only properties near metro")
    food_included: Optional[bool] = Field(None, description="Filter properties with food included")


@tool(args_schema=SearchInput)
def search_properties(
    query: str,
    locality: Optional[str] = None,
    bhk: Optional[int] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    listing_type: Optional[str] = None,
    property_type: Optional[str] = None,
    near_metro: Optional[bool] = None,
    food_included: Optional[bool] = None,
) -> str:
    """Search for properties using semantic search + structured filters."""
    filters = {k: v for k, v in {
        "locality": locality,
        "bhk": bhk,
        "min_price": min_price,
        "max_price": max_price,
        "listing_type": listing_type,
        "property_type": property_type,
        "near_metro": near_metro,
        "food_included": food_included,
    }.items() if v is not None}

    chunks = retrieve(query, n_results=6, filters=filters)
    if not chunks:
        return "No properties found matching the given criteria."

    results = []
    for c in chunks:
        if c.get("chunk_type") == "property":
            results.append({
                "property_id": c.get("property_id"),
                "locality": c.get("locality"),
                "listing_type": c.get("listing_type"),
                "bhk": c.get("bhk"),
                "price": c.get("price"),
                "area_sqft": c.get("area_sqft"),
                "near_metro": bool(c.get("near_metro")),
                "full_details": c["text"],
            })

    return json.dumps(results, ensure_ascii=False)


# ─── Tool 2: get_property_details ────────────────────────────────────────────

class PropertyDetailInput(BaseModel):
    property_id: str = Field(..., description="The property ID (e.g. PROP1001) or item index/number e.g. '1'")


@tool(args_schema=PropertyDetailInput)
def get_property_details(property_id: str) -> str:
    """Get complete details of a specific property including amenities and owner info."""
    with SessionLocal() as session:
        prop = resolve_property_id(property_id, session)
        if not prop:
            return f"Property {property_id} not found."

        amenities = [a.amenity_name for a in prop.amenities]
        owner = prop.owner

        result = {
            "property_id": prop.property_id,
            "title": prop.title,
            "locality": prop.locality,
            "city": prop.city,
            "property_type": prop.property_type,
            "listing_type": prop.listing_type,
            "bhk": prop.bhk,
            "area_sqft": prop.area_sqft,
            "price": prop.price,
            "near_metro": prop.near_metro,
            "metro_distance_km": prop.metro_distance_km,
            "occupancy_type": prop.occupancy_type,
            "gender_preference": prop.gender_preference,
            "food_included": prop.food_included,
            "food_type": prop.food_type,
            "description": prop.description_text,
            "amenities": amenities,
            "owner": {
                "name": owner.full_name if owner else "N/A",
                "email": owner.email if owner else "N/A",
                "phone": owner.phone if owner else "N/A",
            } if owner else None,
        }
        return json.dumps(result, ensure_ascii=False)


# ─── Tool 3: estimate_fair_price ─────────────────────────────────────────────

class FairPriceInput(BaseModel):
    locality: str = Field(..., description="Locality name")
    property_type: str = Field(..., description="APARTMENT, BUILDER_FLOOR, INDEPENDENT_HOUSE, PG")
    bhk: int = Field(..., description="Number of bedrooms")
    area_sqft: float = Field(..., description="Area in square feet")
    listing_type: str = Field(default="SALE", description="RENT or SALE")


@tool(args_schema=FairPriceInput)
def estimate_fair_price(
    locality: str,
    property_type: str,
    bhk: int,
    area_sqft: float,
    listing_type: str = "SALE",
) -> str:
    """Estimate fair market price based on comparable past sales or current rent listings."""
    with SessionLocal() as session:
        if listing_type.upper() == "SALE":
            # Use past sales data
            sales = (
                session.query(PastSale)
                .filter(
                    PastSale.locality.ilike(f"%{locality}%"),
                    PastSale.property_type == property_type.upper(),
                    PastSale.bhk == bhk,
                )
                .all()
            )
            if sales:
                ppsf_values = [s.price_per_sqft for s in sales if s.price_per_sqft > 0]
                if ppsf_values:
                    avg_ppsf = statistics.mean(ppsf_values)
                    estimated = avg_ppsf * area_sqft
                    return json.dumps({
                        "estimated_price": round(estimated),
                        "avg_price_per_sqft": round(avg_ppsf, 2),
                        "comparable_sales": len(sales),
                        "locality": locality,
                        "note": f"Based on {len(sales)} comparable sales in {locality}",
                    })

            # Fallback: locality-wide estimate
            all_sales = session.query(PastSale).filter(
                PastSale.locality.ilike(f"%{locality}%")
            ).all()
            if all_sales:
                avg_ppsf = statistics.mean([s.price_per_sqft for s in all_sales if s.price_per_sqft > 0] or [5000])
                return json.dumps({
                    "estimated_price": round(avg_ppsf * area_sqft),
                    "avg_price_per_sqft": round(avg_ppsf, 2),
                    "comparable_sales": len(all_sales),
                    "note": f"Based on all sales in {locality} (no exact match)",
                })

            return json.dumps({"error": f"Insufficient data for {locality}"})

        else:
            # Rent estimate from current listings
            rents = (
                session.query(Property.price)
                .filter(
                    Property.locality.ilike(f"%{locality}%"),
                    Property.listing_type == "RENT",
                    Property.bhk == bhk,
                )
                .all()
            )
            if rents:
                prices = [r.price for r in rents if r.price > 0]
                avg_rent = statistics.mean(prices) if prices else 0
                return json.dumps({
                    "estimated_rent": round(avg_rent),
                    "comparable_listings": len(prices),
                    "locality": locality,
                    "note": f"Average of {len(prices)} active {bhk}BHK RENT listings in {locality}",
                })
            return json.dumps({"error": f"No RENT data for {locality} {bhk}BHK"})


# ─── Tool 4: compare_properties ──────────────────────────────────────────────

class CompareInput(BaseModel):
    property_ids: list[str] = Field(..., description="List of 2–4 property IDs to compare")


@tool(args_schema=CompareInput)
def compare_properties(property_ids: list[str]) -> str:
    """Compare 2–4 properties side by side with price analysis."""
    if len(property_ids) < 2:
        return "Please provide at least 2 property IDs to compare."
    if len(property_ids) > 4:
        property_ids = property_ids[:4]

    with SessionLocal() as session:
        results = []
        for pid in property_ids:
            prop = resolve_property_id(pid, session)
            if not prop:
                results.append({"property_id": pid, "error": "Not found"})
                continue

            amenities = [a.amenity_name for a in prop.amenities]

            # Get fair price estimate for market rating
            sales = session.query(PastSale).filter(
                PastSale.locality.ilike(f"%{prop.locality}%"),
                PastSale.property_type == prop.property_type,
                PastSale.bhk == prop.bhk,
            ).all()
            market_rating = "unknown"
            if sales:
                ppsf_values = [s.price_per_sqft for s in sales if s.price_per_sqft > 0]
                if ppsf_values and prop.area_sqft:
                    fair_price = statistics.mean(ppsf_values) * prop.area_sqft
                    ratio = prop.price / fair_price if fair_price > 0 else 1
                    if ratio < 0.9:
                        market_rating = "below_market"
                    elif ratio > 1.1:
                        market_rating = "above_market"
                    else:
                        market_rating = "at_market"

            results.append({
                "property_id": prop.property_id,
                "title": prop.title,
                "locality": prop.locality,
                "property_type": prop.property_type,
                "listing_type": prop.listing_type,
                "bhk": prop.bhk,
                "area_sqft": prop.area_sqft,
                "price": prop.price,
                "near_metro": prop.near_metro,
                "metro_distance_km": prop.metro_distance_km,
                "amenities": amenities[:10],
                "market_rating": market_rating,
            })

    return json.dumps(results, ensure_ascii=False)


# ─── Tool 5: schedule_visit (requires confirmation) ───────────────────────────

class ScheduleVisitInput(BaseModel):
    property_id: str = Field(..., description="Property ID to visit. MUST be a valid property ID (e.g. PROP1001) specified by the user or found in conversation history. DO NOT guess or invent a property ID if none is specified.")
    scheduled_datetime: Optional[str] = Field(None, description="Datetime string ONLY if explicitly specified by the user. Do NOT invent a date/time if not mentioned by user.")
    user_name: Optional[str] = Field(None, description="Visitor's full name ONLY if explicitly specified by user.")
    user_email: Optional[str] = Field(None, description="Visitor's email address ONLY if explicitly specified by user.")
    notes: Optional[str] = Field(None, description="Additional notes or requirements")


@tool(args_schema=ScheduleVisitInput)
def schedule_visit(
    property_id: str,
    scheduled_datetime: Optional[str] = None,
    user_name: Optional[str] = None,
    user_email: Optional[str] = None,
    notes: Optional[str] = None,
) -> str:
    """
    Schedule a property visit. REQUIRES user confirmation before execution.
    IMPORTANT: DO NOT invoke this tool if the target property has not been specified by the user. Ask the user about the property first.
    Returns a confirmation_required payload for the frontend.
    """
    with SessionLocal() as session:
        prop = resolve_property_id(property_id, session)
        if not prop:
            return json.dumps({"error": f"Property {property_id} not found."})
        actual_pid = prop.property_id

        # Create as pending_confirmation
        visit = Visit(
            property_id=actual_pid,
            user_name=user_name or "",
            user_email=user_email or "",
            scheduled_datetime=scheduled_datetime or "",
            status="pending_confirmation",
            notes=notes,
        )
        session.add(visit)
        session.commit()
        session.refresh(visit)

        time_str = f" on {scheduled_datetime}" if scheduled_datetime else ""
        return json.dumps({
            "action": "schedule_visit",
            "requires_confirmation": True,
            "visit_id": visit.id,
            "property_id": actual_pid,
            "property_title": prop.title,
            "locality": prop.locality,
            "scheduled_datetime": scheduled_datetime or "",
            "user_name": user_name or "",
            "user_email": user_email or "",
            "message": (
                f"Please review and confirm scheduling a visit for **{prop.title}** in {prop.locality}{time_str}."
            ),
        })


# ─── Tool 6: send_owner_inquiry (requires confirmation) ──────────────────────

class InquiryInput(BaseModel):
    property_id: str = Field(..., description="Property ID to inquire about. MUST be a valid property ID specified by the user or found in conversation history. DO NOT guess or invent a property ID if none is specified.")
    message: Optional[str] = Field(None, description="Message to send to the owner ONLY if specified by the user.")
    user_name: Optional[str] = Field(None, description="Sender's full name ONLY if specified by the user.")


@tool(args_schema=InquiryInput)
def send_owner_inquiry(property_id: str, message: Optional[str] = None, user_name: Optional[str] = None) -> str:
    """
    Send a message inquiry to the property owner. REQUIRES user confirmation.
    IMPORTANT: DO NOT invoke this tool if the target property has not been specified by the user. Ask the user about the property first.
    """
    with SessionLocal() as session:
        prop = resolve_property_id(property_id, session)
        if not prop:
            return json.dumps({"error": f"Property {property_id} not found."})
        actual_pid = prop.property_id

        inquiry = Inquiry(
            property_id=actual_pid,
            owner_id=prop.owner_id,
            message=message or "",
            user_name=user_name or "",
            status="pending_confirmation",
        )
        session.add(inquiry)
        session.commit()
        session.refresh(inquiry)

        owner_name = prop.owner.full_name if prop.owner else "Owner"
        msg_text = (message or "").strip()
        preview = f': "{msg_text[:100]}..."' if msg_text else ""
        return json.dumps({
            "action": "send_owner_inquiry",
            "requires_confirmation": True,
            "inquiry_id": inquiry.id,
            "property_id": actual_pid,
            "property_title": prop.title,
            "owner_name": owner_name,
            "user_name": user_name or "",
            "message_preview": msg_text[:200],
            "message": (
                f"Please review and confirm sending an inquiry to {owner_name} regarding **{prop.title}**{preview}."
            ),
        })




# ─── Tool 7: cancel_visit ─────────────────────────────────────────────────────

class CancelVisitInput(BaseModel):
    property_id: str = Field(..., description="Property ID or number for which to cancel the scheduled visit (e.g. PROP1001 or 1007).")
    visit_id: Optional[int] = Field(None, description="Optional specific visit ID to cancel.")


@tool(args_schema=CancelVisitInput)
def cancel_visit(property_id: str, visit_id: Optional[int] = None) -> str:
    """
    Cancel and remove a scheduled visit for a given property.
    Deletes the visit schedule from the database so it is removed from the Activity tab.
    """
    if not visit_id and not str(property_id or "").strip():
        return json.dumps({
            "status": "error",
            "message": "A property ID or visit ID is required to cancel a visit."
        })

    with SessionLocal() as session:
        prop = resolve_property_id(property_id, session)
        target_pid = prop.property_id if prop else (f"PROP{property_id}" if str(property_id).isdigit() else property_id)

        query = session.query(Visit)
        if visit_id:
            query = query.filter(Visit.id == visit_id)
        else:
            query = query.filter(
                (Visit.property_id == target_pid) |
                (Visit.property_id.ilike(f"%{property_id}%"))
            )

        visits = query.all()
        if not visits:
            # Fallback search if any visits exist in the DB
            alt_pid = f"PROP{property_id}" if str(property_id).isdigit() else property_id
            visits = session.query(Visit).filter(Visit.property_id == alt_pid).all()

        if not visits:
            return json.dumps({
                "status": "not_found",
                "message": f"No active scheduled visits found for property {property_id}."
            })

        count = len(visits)
        for v in visits:
            session.delete(v)

        session.commit()

        return json.dumps({
            "status": "success",
            "cancelled_count": count,
            "property_id": target_pid,
            "message": f"Successfully cancelled and removed {count} scheduled visit(s) for property {target_pid}."
        })


# Export tool list
ALL_TOOLS = [
    search_properties,
    get_property_details,
    estimate_fair_price,
    compare_properties,
    schedule_visit,
    send_owner_inquiry,
    cancel_visit
]

# Tools that require confirmation
CONFIRMATION_REQUIRED_TOOLS = {"schedule_visit", "send_owner_inquiry"}
