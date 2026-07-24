"""
reports.py — PDF report download endpoint.
"""
from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.database import Report, get_db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/{report_id}")
def download_report(report_id: int, db: Session = Depends(get_db)):
    """Download a generated PDF comparison report."""
    report = db.query(Report).filter(Report.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found.")

    file_path = Path(report.file_path)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Report file not found on disk.")

    return FileResponse(
        path=str(file_path),
        media_type="application/pdf",
        filename=file_path.name,
    )


@router.get("")
def list_reports(
    user_identifier: str | None = None,
    db: Session = Depends(get_db),
):
    """List all generated reports."""
    q = db.query(Report)
    if user_identifier:
        q = q.filter(Report.user_identifier == user_identifier)
    reports = q.order_by(Report.created_at.desc()).limit(50).all()
    return [
        {
            "id": r.id,
            "user_identifier": r.user_identifier,
            "property_ids": r.property_ids,
            "created_at": str(r.created_at),
            "download_url": f"/reports/{r.id}",
        }
        for r in reports
    ]
