"""
report.py — ReportLab PDF comparison report for 2–4 properties.
"""
from __future__ import annotations

import json
import os
import statistics
import uuid
from pathlib import Path
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    HRFlowable, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
)

from app.config import REPORTS_PATH
from app.database import Property, PastSale, SessionLocal

# ─── Colour palette ───────────────────────────────────────────────────────────
NAVY = colors.HexColor("#0F172A")
ELECTRIC = colors.HexColor("#3B82F6")
GOLD = colors.HexColor("#F59E0B")
GREEN = colors.HexColor("#22C55E")
RED = colors.HexColor("#EF4444")
YELLOW = colors.HexColor("#EAB308")
LIGHT_BG = colors.HexColor("#F8FAFC")
HEADER_BG = colors.HexColor("#1E3A5F")
SUBHEADER_BG = colors.HexColor("#E2E8F0")
WHITE = colors.white


def _market_rating(prop: Property, session) -> tuple[str, Any]:
    sales = session.query(PastSale).filter(
        PastSale.locality.ilike(f"%{prop.locality}%"),
        PastSale.property_type == prop.property_type,
        PastSale.bhk == prop.bhk,
    ).all()
    if not sales or not prop.area_sqft:
        return "Unknown", LIGHT_BG

    ppsf = statistics.mean([s.price_per_sqft for s in sales if s.price_per_sqft > 0] or [0])
    if ppsf == 0:
        return "Unknown", LIGHT_BG

    fair = ppsf * prop.area_sqft
    ratio = prop.price / fair
    if ratio < 0.9:
        return f"🟢 Below Market ({ratio:.0%})", GREEN
    elif ratio > 1.1:
        return f"🔴 Above Market ({ratio:.0%})", RED
    else:
        return f"🟡 At Market ({ratio:.0%})", YELLOW


def create_comparison_pdf(
    property_ids: list[str],
    user_identifier: str = "anonymous",
) -> tuple[str, dict]:
    """
    Generate PDF comparison report.
    Returns (file_path, metadata_dict).
    """
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "Title", parent=styles["Title"],
        fontSize=22, textColor=WHITE, spaceAfter=4, fontName="Helvetica-Bold"
    )
    subtitle_style = ParagraphStyle(
        "Subtitle", parent=styles["Normal"],
        fontSize=10, textColor=LIGHT_BG, spaceAfter=2
    )
    label_style = ParagraphStyle(
        "Label", parent=styles["Normal"],
        fontSize=9, textColor=NAVY, fontName="Helvetica-Bold"
    )
    cell_style = ParagraphStyle(
        "Cell", parent=styles["Normal"],
        fontSize=9, textColor=NAVY,
    )
    note_style = ParagraphStyle(
        "Note", parent=styles["Normal"],
        fontSize=8, textColor=colors.grey,
    )

    # ── Fetch data ────────────────────────────────────────────────────────────
    with SessionLocal() as session:
        props = []
        for pid in property_ids:
            p = session.query(Property).filter(Property.property_id == pid).first()
            if p:
                amenities = [a.amenity_name for a in p.amenities]
                rating_text, rating_color = _market_rating(p, session)
                props.append({
                    "obj": p,
                    "amenities": amenities,
                    "market_rating": rating_text,
                    "rating_color": rating_color,
                })

    if not props:
        raise ValueError("No valid properties found for comparison.")

    # ── Build PDF ─────────────────────────────────────────────────────────────
    report_id = str(uuid.uuid4())[:8]
    filename = f"comparison_{report_id}.pdf"
    file_path = str(Path(REPORTS_PATH) / filename)

    doc = SimpleDocTemplate(
        file_path,
        pagesize=landscape(A4),
        rightMargin=15 * mm,
        leftMargin=15 * mm,
        topMargin=15 * mm,
        bottomMargin=15 * mm,
    )

    story = []

    # ── Header banner ─────────────────────────────────────────────────────────
    header_data = [
        [Paragraph("PropFind Property Comparison Report", title_style)],
        [Paragraph(f"Generated for: {user_identifier}   |   Properties: {len(props)}", subtitle_style)],
    ]
    header_table = Table(header_data, colWidths=[doc.width])
    header_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), HEADER_BG),
        ("TOPPADDING", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ("LEFTPADDING", (0, 0), (-1, -1), 15),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 6 * mm))

    # ── Comparison table ──────────────────────────────────────────────────────
    col_width = doc.width / (len(props) + 1)

    def fmt_price(p, listing_type):
        if listing_type in ("RENT", "PG"):
            return f"₹{p:,.0f}/mo"
        val = p
        if val >= 10_000_000:
            return f"₹{val/10_000_000:.2f} Cr"
        elif val >= 100_000:
            return f"₹{val/100_000:.2f} L"
        return f"₹{val:,.0f}"

    rows = [
        # Header row
        [Paragraph("Feature", label_style)]
        + [Paragraph(d["obj"].title or d["obj"].property_id, label_style) for d in props],

        [Paragraph("Property ID", label_style)]
        + [Paragraph(d["obj"].property_id, cell_style) for d in props],

        [Paragraph("Locality", label_style)]
        + [Paragraph(d["obj"].locality or "—", cell_style) for d in props],

        [Paragraph("Type", label_style)]
        + [Paragraph(d["obj"].property_type.replace("_", " ").title(), cell_style) for d in props],

        [Paragraph("Listing", label_style)]
        + [Paragraph(d["obj"].listing_type, cell_style) for d in props],

        [Paragraph("BHK", label_style)]
        + [Paragraph(str(d["obj"].bhk), cell_style) for d in props],

        [Paragraph("Area (sq.ft)", label_style)]
        + [Paragraph(f"{d['obj'].area_sqft:.0f}", cell_style) for d in props],

        [Paragraph("Price", label_style)]
        + [Paragraph(fmt_price(d["obj"].price, d["obj"].listing_type), cell_style) for d in props],

        [Paragraph("Near Metro", label_style)]
        + [Paragraph("✅ Yes" if d["obj"].near_metro else "❌ No", cell_style) for d in props],

        [Paragraph("Metro Dist (km)", label_style)]
        + [Paragraph(f"{d['obj'].metro_distance_km:.1f}" if d["obj"].metro_distance_km else "—", cell_style) for d in props],

        [Paragraph("Market Rating", label_style)]
        + [Paragraph(d["market_rating"], cell_style) for d in props],

        [Paragraph("Top Amenities", label_style)]
        + [Paragraph(", ".join(d["amenities"][:5]) or "None", cell_style) for d in props],
    ]

    col_widths = [col_width] * (len(props) + 1)
    tbl = Table(rows, colWidths=col_widths, repeatRows=1)

    table_style = TableStyle([
        # Header row
        ("BACKGROUND", (0, 0), (-1, 0), HEADER_BG),
        ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 10),

        # Feature label column
        ("BACKGROUND", (0, 1), (0, -1), SUBHEADER_BG),
        ("FONTNAME", (0, 1), (0, -1), "Helvetica-Bold"),

        # Alternating rows
        *[
            ("BACKGROUND", (1, i), (-1, i), LIGHT_BG if i % 2 == 0 else WHITE)
            for i in range(1, len(rows))
        ],

        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [LIGHT_BG, WHITE]),
    ])
    tbl.setStyle(table_style)
    story.append(tbl)
    story.append(Spacer(1, 6 * mm))

    # ── Footer note ───────────────────────────────────────────────────────────
    story.append(HRFlowable(width="100%", thickness=1, color=ELECTRIC))
    story.append(Spacer(1, 3 * mm))
    story.append(Paragraph(
        "Market ratings are calculated based on past sales data for the same locality, BHK, and property type. "
        "🟢 Below Market = priced more than 10% below fair estimate. 🔴 Above Market = more than 10% above. "
        "🟡 At Market = within ±10%. This report is for informational purposes only.",
        note_style,
    ))

    doc.build(story)
    return file_path, {"report_id": report_id, "file_path": file_path}
