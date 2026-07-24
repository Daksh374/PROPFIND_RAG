"""
properties.py — Property CRUD and search endpoints.
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import Property, PropertyAmenity, Owner, get_db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/properties", tags=["properties"])


def _prop_to_dict(prop: Property, include_owner: bool = False) -> dict:
    d = {
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
        "description_text": prop.description_text,
        "created_at": str(prop.created_at) if prop.created_at else None,
        "amenities": [a.amenity_name for a in prop.amenities],
    }
    if include_owner and prop.owner:
        d["owner"] = {
            "name": prop.owner.full_name,
            "email": prop.owner.email,
            "phone": prop.owner.phone,
        }
    return d


@router.get("")
def list_properties(
    locality: Optional[str] = Query(None),
    bhk: Optional[int] = Query(None),
    min_price: Optional[float] = Query(None),
    max_price: Optional[float] = Query(None),
    listing_type: Optional[str] = Query(None),
    property_type: Optional[str] = Query(None),
    near_metro: Optional[bool] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """Paginated + filtered property listing."""
    q = db.query(Property)

    if locality:
        q = q.filter(Property.locality.ilike(f"%{locality}%"))
    if bhk is not None:
        q = q.filter(Property.bhk == bhk)
    if min_price is not None:
        q = q.filter(Property.price >= min_price)
    if max_price is not None:
        q = q.filter(Property.price <= max_price)
    if listing_type:
        q = q.filter(Property.listing_type == listing_type.upper())
    if property_type:
        q = q.filter(Property.property_type == property_type.upper())
    if near_metro is not None:
        q = q.filter(Property.near_metro == near_metro)

    total = q.count()
    props = q.offset((page - 1) * page_size).limit(page_size).all()

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "results": [_prop_to_dict(p) for p in props],
    }


@router.get("/localities")
def list_localities(db: Session = Depends(get_db)):
    """Return all unique localities."""
    rows = db.query(Property.locality).distinct().order_by(Property.locality).all()
    return [r.locality for r in rows if r.locality]


@router.get("/amenities/top")
def top_amenities(limit: int = Query(10, ge=1, le=50), db: Session = Depends(get_db)):
    """Return top N most common amenities."""
    from sqlalchemy import func
    rows = (
        db.query(PropertyAmenity.amenity_name, func.count(PropertyAmenity.amenity_name).label("cnt"))
        .group_by(PropertyAmenity.amenity_name)
        .order_by(func.count(PropertyAmenity.amenity_name).desc())
        .limit(limit)
        .all()
    )
    return [{"amenity": r.amenity_name, "count": r.cnt} for r in rows]


@router.get("/{property_id}")
def get_property(property_id: str, db: Session = Depends(get_db)):
    """Get full property details including owner."""
    prop = db.query(Property).filter(Property.property_id == property_id).first()
    if not prop:
        raise HTTPException(status_code=404, detail=f"Property {property_id} not found.")
    return _prop_to_dict(prop, include_owner=True)


@router.get("/{property_id}/amenities")
def get_amenities(property_id: str, db: Session = Depends(get_db)):
    """Get all amenities for a property."""
    amns = db.query(PropertyAmenity).filter(PropertyAmenity.property_id == property_id).all()
    return [a.amenity_name for a in amns]
