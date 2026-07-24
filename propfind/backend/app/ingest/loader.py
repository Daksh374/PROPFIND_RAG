"""
loader.py — Reads all 7 CSVs and loads them into SQLite via SQLAlchemy.
Adapter layer merges/normalises columns as needed without modifying source files.
"""
from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

import pandas as pd

from app.config import DATASET_PATH
from app.database import (
    Owner, Property, PropertyAmenity, PastSale,
    TenantHistory, VisitScheduleCSV, SessionLocal, init_db
)

logger = logging.getLogger(__name__)


def _parse_bool(val) -> bool:
    if isinstance(val, bool):
        return val
    return str(val).strip().lower() in ("true", "1", "yes")


def _parse_dt(val) -> datetime | None:
    if pd.isna(val):
        return None
    try:
        return pd.to_datetime(val).to_pydatetime()
    except Exception:
        return None


def load_all(dataset_path: Path | None = None) -> dict[str, int]:
    """
    Load all CSV files into SQLite.
    Returns a dict of table → row count inserted.
    """
    init_db()
    dp = Path(dataset_path or DATASET_PATH)
    counts: dict[str, int] = {}

    with SessionLocal() as session:
        # ── 1. Owners ────────────────────────────────────────────────────────
        owners_df = pd.read_csv(dp / "delhi_ncr_owners.csv")
        existing_owners = {o.owner_id for o in session.query(Owner.owner_id).all()}
        new_owners = [
            Owner(
                owner_id=row["owner_id"],
                full_name=row["full_name"],
                email=row["email"],
                phone=str(row["phone"]),
                role=row.get("role", ""),
                preferred_locality=row.get("preferred_locality", ""),
                created_at=_parse_dt(row.get("created_at")),
            )
            for _, row in owners_df.iterrows()
            if row["owner_id"] not in existing_owners
        ]
        session.bulk_save_objects(new_owners)
        session.commit()
        counts["owners"] = len(new_owners)
        logger.info(f"Loaded {len(new_owners)} owners")

        # ── 2. Properties ────────────────────────────────────────────────────
        props_df = pd.read_csv(dp / "delhi_ncr_properties.csv")
        existing_props = {p.property_id for p in session.query(Property.property_id).all()}
        new_props = []
        for _, row in props_df.iterrows():
            if row["property_id"] in existing_props:
                continue
            new_props.append(Property(
                property_id=row["property_id"],
                owner_id=row["owner_id"],
                title=row.get("title", ""),
                locality=row.get("locality", ""),
                city=row.get("city", "Delhi NCR"),
                property_type=row.get("property_type", "APARTMENT"),
                listing_type=row.get("listing_type", "RENT"),
                bhk=int(row["bhk"]) if not pd.isna(row["bhk"]) else 1,
                area_sqft=float(row["area_sqft"]) if not pd.isna(row["area_sqft"]) else 0.0,
                price=float(row["price"]) if not pd.isna(row["price"]) else 0.0,
                near_metro=_parse_bool(row.get("near_metro", False)),
                metro_distance_km=float(row["metro_distance_km"]) if not pd.isna(row.get("metro_distance_km", float("nan"))) else None,
                occupancy_type=row.get("occupancy_type", ""),
                gender_preference=row.get("gender_preference", "ANY"),
                food_included=_parse_bool(row.get("food_included", False)),
                food_type=row.get("food_type", "NONE"),
                description_text=row.get("description_text", ""),
                created_at=_parse_dt(row.get("created_at")),
            ))
        session.bulk_save_objects(new_props)
        session.commit()
        counts["properties"] = len(new_props)
        logger.info(f"Loaded {len(new_props)} properties")

        # ── 3. Amenities ─────────────────────────────────────────────────────
        amenities_df = pd.read_csv(dp / "delhi_ncr_property_amenities.csv")
        existing_amn = {a.amenity_id for a in session.query(PropertyAmenity.amenity_id).all()}
        new_amn = [
            PropertyAmenity(
                amenity_id=row["amenity_id"],
                property_id=row["property_id"],
                amenity_name=row["amenity_name"],
            )
            for _, row in amenities_df.iterrows()
            if row["amenity_id"] not in existing_amn
        ]
        session.bulk_save_objects(new_amn)
        session.commit()
        counts["amenities"] = len(new_amn)
        logger.info(f"Loaded {len(new_amn)} amenities")

        # ── 4. Past Sales ────────────────────────────────────────────────────
        sales_df = pd.read_csv(dp / "delhi_ncr_past_sales.csv")
        existing_sales = {s.sale_id for s in session.query(PastSale.sale_id).all()}
        new_sales = [
            PastSale(
                sale_id=row["sale_id"],
                locality=row.get("locality", ""),
                city=row.get("city", "Delhi NCR"),
                property_type=row.get("property_type", ""),
                bhk=int(row["bhk"]) if not pd.isna(row["bhk"]) else 1,
                area_sqft=float(row["area_sqft"]) if not pd.isna(row["area_sqft"]) else 0.0,
                sold_price=float(row["sold_price"]) if not pd.isna(row["sold_price"]) else 0.0,
                price_per_sqft=float(row["price_per_sqft"]) if not pd.isna(row["price_per_sqft"]) else 0.0,
                sold_date=str(row.get("sold_date", "")),
            )
            for _, row in sales_df.iterrows()
            if row["sale_id"] not in existing_sales
        ]
        session.bulk_save_objects(new_sales)
        session.commit()
        counts["past_sales"] = len(new_sales)
        logger.info(f"Loaded {len(new_sales)} past sales")

        # ── 5. Tenant History ────────────────────────────────────────────────
        th_df = pd.read_csv(dp / "delhi_ncr_tenant_history.csv")
        existing_th = {t.tenant_history_id for t in session.query(TenantHistory.tenant_history_id).all()}
        new_th = [
            TenantHistory(
                tenant_history_id=row["tenant_history_id"],
                property_id=row["property_id"],
                locality=row.get("locality", ""),
                bhk=int(row["bhk"]) if not pd.isna(row["bhk"]) else 1,
                monthly_rent=float(row["monthly_rent"]) if not pd.isna(row["monthly_rent"]) else 0.0,
                lease_start_date=str(row.get("lease_start_date", "")),
                lease_end_date=str(row.get("lease_end_date", "")),
                occupancy_status=row.get("occupancy_status", ""),
                tenant_name=row.get("tenant_name", ""),
                created_at=_parse_dt(row.get("created_at")),
            )
            for _, row in th_df.iterrows()
            if row["tenant_history_id"] not in existing_th
        ]
        session.bulk_save_objects(new_th)
        session.commit()
        counts["tenant_history"] = len(new_th)
        logger.info(f"Loaded {len(new_th)} tenant history records")

        # ── 6. Visit Schedules (CSV reference) ──────────────────────────────
        vs_df = pd.read_csv(dp / "delhi_ncr_visit_schedules.csv")
        existing_vs = {v.visit_id for v in session.query(VisitScheduleCSV.visit_id).all()}
        new_vs = [
            VisitScheduleCSV(
                visit_id=row["visit_id"],
                property_id=row["property_id"],
                owner_id=row.get("owner_id", ""),
                user_name=row.get("user_name", ""),
                user_email=row.get("user_email", ""),
                user_phone=str(row.get("user_phone", "")),
                scheduled_time=str(row.get("scheduled_time", "")),
                status=row.get("status", ""),
                notes=row.get("notes", ""),
                created_at=_parse_dt(row.get("created_at")),
            )
            for _, row in vs_df.iterrows()
            if row["visit_id"] not in existing_vs
        ]
        session.bulk_save_objects(new_vs)
        session.commit()
        counts["visit_schedules"] = len(new_vs)
        logger.info(f"Loaded {len(new_vs)} visit schedule records")

    return counts
