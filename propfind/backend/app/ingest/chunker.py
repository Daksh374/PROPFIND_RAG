"""
chunker.py — Builds natural-language text chunks for ChromaDB indexing.

Two kinds of documents:
  1. Per-property chunk — enriched with amenities, owner info, sales history
  2. Per-locality chunk — aggregated stats paragraph for locality-level queries
"""
from __future__ import annotations

import logging
from typing import Generator

import pandas as pd
from sqlalchemy import func, text

from app.database import (
    Property, PropertyAmenity, Owner, PastSale,
    TenantHistory, SessionLocal
)

logger = logging.getLogger(__name__)

ChunkTuple = tuple[str, dict]  # (text, metadata)


def iter_property_chunks(session) -> Generator[ChunkTuple, None, None]:
    """
    Yield one (text, metadata) tuple per property.
    """
    props = (
        session.query(Property)
        .outerjoin(Owner, Property.owner_id == Owner.owner_id)
        .all()
    )

    for prop in props:
        amenity_names = [a.amenity_name for a in prop.amenities]
        amenity_str = ", ".join(amenity_names) if amenity_names else "None listed"

        listing_label = {
            "RENT": "available for rent",
            "SALE": "available for sale",
            "PG": "available as PG accommodation",
        }.get(prop.listing_type, prop.listing_type)

        metro_info = (
            f"Located {prop.metro_distance_km:.1f} km from nearest metro."
            if prop.metro_distance_km is not None
            else "Metro distance not specified."
        )
        metro_badge = "Near metro." if prop.near_metro else ""

        owner_info = ""
        if prop.owner:
            owner_info = (
                f"Owner: {prop.owner.full_name} "
                f"(📞 {prop.owner.phone}, ✉ {prop.owner.email})."
            )

        food_info = ""
        if prop.listing_type == "PG":
            food_info = (
                f"Food {'included' if prop.food_included else 'not included'}."
                + (f" Food type: {prop.food_type}." if prop.food_included else "")
            )
            gender_info = f"Gender preference: {prop.gender_preference}."
            occupancy_info = f"Occupancy type: {prop.occupancy_type}."
        else:
            gender_info = ""
            occupancy_info = ""

        price_label = "₹{:,.0f}".format(prop.price) if prop.listing_type != "SALE" else "₹{:,.0f}".format(prop.price)
        price_suffix = "/month" if prop.listing_type == "RENT" else ("/month" if prop.listing_type == "PG" else "")

        chunk_text = (
            f"{prop.title}. "
            f"This {prop.bhk} BHK {prop.property_type.replace('_', ' ').title()} is {listing_label} "
            f"in {prop.locality}, {prop.city}. "
            f"Area: {prop.area_sqft:.0f} sq.ft. "
            f"Price: {price_label}{price_suffix}. "
            f"{metro_info} {metro_badge} "
            f"Amenities: {amenity_str}. "
            f"{food_info} {gender_info} {occupancy_info} "
            f"{owner_info} "
            f"{prop.description_text or ''}"
        ).strip()

        metadata = {
            "property_id": prop.property_id,
            "locality": prop.locality,
            "city": prop.city,
            "property_type": prop.property_type,
            "listing_type": prop.listing_type,
            "bhk": prop.bhk,
            "area_sqft": prop.area_sqft or 0.0,
            "price": prop.price or 0.0,
            "near_metro": int(prop.near_metro or 0),
            "metro_distance_km": prop.metro_distance_km or 99.0,
            "chunk_type": "property",
        }

        yield chunk_text, metadata


def iter_locality_chunks(session) -> Generator[ChunkTuple, None, None]:
    """
    Yield one aggregated NL paragraph per unique locality.
    """
    rows = session.execute(text("""
        SELECT
            p.locality,
            COUNT(p.property_id)                                        AS total_listings,
            ROUND(AVG(p.price), 0)                                      AS avg_price,
            ROUND(MIN(p.price), 0)                                      AS min_price,
            ROUND(MAX(p.price), 0)                                      AS max_price,
            GROUP_CONCAT(DISTINCT p.property_type)                      AS property_types,
            GROUP_CONCAT(DISTINCT p.listing_type)                       AS listing_types,
            SUM(CASE WHEN p.near_metro = 1 THEN 1 ELSE 0 END)          AS metro_count,
            ROUND(AVG(p.metro_distance_km), 2)                         AS avg_metro_dist,
            GROUP_CONCAT(DISTINCT p.bhk)                                AS bhk_options
        FROM properties p
        GROUP BY p.locality
    """)).fetchall()

    sales_rows = session.execute(text("""
        SELECT locality, ROUND(AVG(price_per_sqft), 0) AS avg_ppsf, COUNT(*) AS sale_count
        FROM past_sales
        GROUP BY locality
    """)).fetchall()
    sales_map = {r.locality: r for r in sales_rows}

    for r in rows:
        locality = r.locality
        types_str = r.property_types.replace(",", ", ") if r.property_types else "various types"
        listings_str = r.listing_types.replace(",", "/") if r.listing_types else "RENT/SALE"
        bhk_str = "/".join(sorted(set(r.bhk_options.split(",")))) if r.bhk_options else "1-5"

        metro_pct = int(r.metro_count * 100 / r.total_listings) if r.total_listings else 0

        sales_info = ""
        if locality in sales_map:
            sm = sales_map[locality]
            sales_info = (
                f"Based on {sm.sale_count} recent sales, average price per sq.ft is "
                f"₹{sm.avg_ppsf:,.0f}. "
            )

        chunk_text = (
            f"Locality: {locality}. "
            f"Total active listings: {r.total_listings}. "
            f"Property types available: {types_str}. "
            f"Listing types: {listings_str}. "
            f"BHK options: {bhk_str} BHK. "
            f"Average price: ₹{r.avg_price:,.0f} "
            f"(range: ₹{r.min_price:,.0f} – ₹{r.max_price:,.0f}). "
            f"Average metro distance: {r.avg_metro_dist:.1f} km; "
            f"{metro_pct}% of listings are near a metro station. "
            f"{sales_info}"
        ).strip()

        metadata = {
            "locality": locality,
            "total_listings": r.total_listings,
            "avg_price": float(r.avg_price or 0),
            "chunk_type": "locality",
        }

        yield chunk_text, metadata


def build_all_chunks() -> list[ChunkTuple]:
    """Return all property + locality chunks."""
    chunks: list[ChunkTuple] = []
    with SessionLocal() as session:
        prop_chunks = list(iter_property_chunks(session))
        loc_chunks = list(iter_locality_chunks(session))
    chunks.extend(prop_chunks)
    chunks.extend(loc_chunks)
    logger.info(f"Built {len(prop_chunks)} property chunks + {len(loc_chunks)} locality chunks")
    return chunks
