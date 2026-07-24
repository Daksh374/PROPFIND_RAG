"""
database.py — SQLAlchemy models and engine setup.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from sqlalchemy import (
    Boolean, Column, DateTime, Float, ForeignKey,
    Integer, String, Text, create_engine, event
)
from sqlalchemy.orm import DeclarativeBase, relationship, sessionmaker

from app.config import DATABASE_URL

# Ensure the data directory exists
_db_path = DATABASE_URL.replace("sqlite:///", "")
Path(_db_path).parent.mkdir(parents=True, exist_ok=True)

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
    echo=False,
)

# Enable WAL mode for SQLite concurrency
@event.listens_for(engine, "connect")
def set_wal_mode(dbapi_conn, _):
    dbapi_conn.execute("PRAGMA journal_mode=WAL")
    dbapi_conn.execute("PRAGMA foreign_keys=ON")


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


# ─── CSV-sourced tables ──────────────────────────────────────────────────────

class Owner(Base):
    __tablename__ = "owners"

    owner_id = Column(String, primary_key=True)
    full_name = Column(String)
    email = Column(String)
    phone = Column(String)
    role = Column(String)
    preferred_locality = Column(String)
    created_at = Column(DateTime)

    properties = relationship("Property", back_populates="owner")
    inquiries = relationship("Inquiry", back_populates="owner")


class Property(Base):
    __tablename__ = "properties"

    property_id = Column(String, primary_key=True)
    owner_id = Column(String, ForeignKey("owners.owner_id"))
    title = Column(String)
    locality = Column(String)
    city = Column(String)
    property_type = Column(String)
    listing_type = Column(String)
    bhk = Column(Integer)
    area_sqft = Column(Float)
    price = Column(Float)
    near_metro = Column(Boolean)
    metro_distance_km = Column(Float)
    occupancy_type = Column(String)
    gender_preference = Column(String)
    food_included = Column(Boolean)
    food_type = Column(String)
    description_text = Column(Text)
    created_at = Column(DateTime)

    owner = relationship("Owner", back_populates="properties")
    amenities = relationship("PropertyAmenity", back_populates="property")
    visits = relationship("Visit", back_populates="property")
    inquiries = relationship("Inquiry", back_populates="property")
    tenant_history = relationship("TenantHistory", back_populates="property")


class PropertyAmenity(Base):
    __tablename__ = "property_amenities"

    amenity_id = Column(String, primary_key=True)
    property_id = Column(String, ForeignKey("properties.property_id"))
    amenity_name = Column(String)

    property = relationship("Property", back_populates="amenities")


class PastSale(Base):
    __tablename__ = "past_sales"

    sale_id = Column(String, primary_key=True)
    locality = Column(String)
    city = Column(String)
    property_type = Column(String)
    bhk = Column(Integer)
    area_sqft = Column(Float)
    sold_price = Column(Float)
    price_per_sqft = Column(Float)
    sold_date = Column(String)


class TenantHistory(Base):
    __tablename__ = "tenant_history"

    tenant_history_id = Column(String, primary_key=True)
    property_id = Column(String, ForeignKey("properties.property_id"))
    locality = Column(String)
    bhk = Column(Integer)
    monthly_rent = Column(Float)
    lease_start_date = Column(String)
    lease_end_date = Column(String)
    occupancy_status = Column(String)
    tenant_name = Column(String)
    created_at = Column(DateTime)

    property = relationship("Property", back_populates="tenant_history")


class VisitScheduleCSV(Base):
    """Read-only reference table loaded from the CSV."""
    __tablename__ = "visit_schedules_csv"

    visit_id = Column(String, primary_key=True)
    property_id = Column(String)
    owner_id = Column(String)
    user_name = Column(String)
    user_email = Column(String)
    user_phone = Column(String)
    scheduled_time = Column(String)
    status = Column(String)
    notes = Column(Text)
    created_at = Column(DateTime)


# ─── Agent-generated tables ──────────────────────────────────────────────────

class Visit(Base):
    __tablename__ = "visits"

    id = Column(Integer, primary_key=True, autoincrement=True)
    property_id = Column(String, ForeignKey("properties.property_id"))
    user_name = Column(String)
    user_email = Column(String)
    scheduled_datetime = Column(String)
    status = Column(String, default="pending_confirmation")  # pending_confirmation | scheduled | cancelled | completed
    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

    property = relationship("Property", back_populates="visits")


class Inquiry(Base):
    __tablename__ = "inquiries"

    id = Column(Integer, primary_key=True, autoincrement=True)
    property_id = Column(String, ForeignKey("properties.property_id"))
    owner_id = Column(String, ForeignKey("owners.owner_id"))
    message = Column(Text)
    user_name = Column(String)
    status = Column(String, default="pending_confirmation")  # pending_confirmation | sent | cancelled
    created_at = Column(DateTime, default=datetime.utcnow)

    property = relationship("Property", back_populates="inquiries")
    owner = relationship("Owner", back_populates="inquiries")


class UserMemory(Base):
    __tablename__ = "user_memory"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_identifier = Column(String, index=True)
    key = Column(String)
    value = Column(String)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Report(Base):
    __tablename__ = "reports"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_identifier = Column(String)
    property_ids = Column(Text)  # JSON list
    file_path = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)


def init_db():
    """Create all tables if they don't exist."""
    Base.metadata.create_all(bind=engine)


def get_db():
    """FastAPI dependency — yields a DB session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
