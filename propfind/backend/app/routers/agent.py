"""
agent.py — Agent action endpoints (search, compare, visits, inquiries).
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import Visit, Inquiry, get_db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/agent", tags=["agent"])


class SearchRequest(BaseModel):
    query: str
    user_identifier: str = "anonymous"
    filters: dict | None = None


class CompareRequest(BaseModel):
    property_ids: list[str]
    user_identifier: str = "anonymous"


@router.post("/search")
def agent_search(req: SearchRequest):
    """Run agent search tool directly."""
    from app.agent.tools import search_properties
    result = search_properties.invoke({"query": req.query, **(req.filters or {})})
    return {"result": result}


@router.post("/compare")
def agent_compare(req: CompareRequest):
    """Compare properties via agent tool."""
    from app.agent.tools import compare_properties
    result = compare_properties.invoke({"property_ids": req.property_ids})
    return {"result": result}


@router.get("/visits")
def list_visits(
    user_identifier: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """List all scheduled visits."""
    q = db.query(Visit)
    if user_identifier:
        q = q.filter(Visit.user_email.ilike(f"%{user_identifier}%"))
    visits = q.order_by(Visit.created_at.desc()).limit(100).all()
    return [
        {
            "id": v.id,
            "property_id": v.property_id,
            "user_name": v.user_name,
            "user_email": v.user_email,
            "scheduled_datetime": v.scheduled_datetime,
            "status": v.status,
            "notes": v.notes,
            "created_at": str(v.created_at),
        }
        for v in visits
    ]


@router.get("/inquiries")
def list_inquiries(
    user_identifier: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """List all owner inquiries."""
    q = db.query(Inquiry)
    if user_identifier:
        q = q.filter(Inquiry.user_name.ilike(f"%{user_identifier}%"))
    inquiries = q.order_by(Inquiry.created_at.desc()).limit(100).all()
    return [
        {
            "id": i.id,
            "property_id": i.property_id,
            "owner_id": i.owner_id,
            "message": i.message,
            "user_name": i.user_name,
            "status": i.status,
            "created_at": str(i.created_at),
        }
        for i in inquiries
    ]


@router.delete("/inquiries")
def delete_all_inquiries(
    db: Session = Depends(get_db),
):
    """Delete all owner inquiries from DB."""
    count = db.query(Inquiry).delete()
    db.commit()
    return {"message": f"Successfully deleted {count} inquiries.", "deleted_count": count}


@router.delete("/inquiries/{inquiry_id}")
def delete_inquiry(
    inquiry_id: int,
    db: Session = Depends(get_db),
):
    """Delete single inquiry by ID."""
    inquiry = db.query(Inquiry).filter(Inquiry.id == inquiry_id).first()
    if not inquiry:
        raise HTTPException(status_code=404, detail="Inquiry not found.")
    db.delete(inquiry)
    db.commit()
    return {"message": "Inquiry deleted successfully.", "id": inquiry_id}


@router.delete("/visits")
def delete_all_visits(
    db: Session = Depends(get_db),
):
    """Delete all scheduled visits from DB."""
    count = db.query(Visit).delete()
    db.commit()
    return {"message": f"Successfully deleted {count} visits.", "deleted_count": count}


@router.delete("/visits/{visit_id}")
def delete_visit(
    visit_id: int,
    db: Session = Depends(get_db),
):
    """Delete single visit by ID."""
    visit = db.query(Visit).filter(Visit.id == visit_id).first()
    if not visit:
        raise HTTPException(status_code=404, detail="Visit not found.")
    db.delete(visit)
    db.commit()
    return {"message": "Visit deleted successfully.", "id": visit_id}

