"""Full-vehicle inspection: aggregate multi-photo assessments into a professional
condition report (Pro feature) — designed for pre-purchase used-car checks.

Current signals (from your trained models):
  - visible damage per angle, severity, repair cost

Plug-in point for future models (see `extra_checks`):
  - repaint / panel-respray detection
  - panel-gap inconsistency (replaced parts)
  - accident-history classifier
Train those and register a callable; the report format already supports findings.
"""
from __future__ import annotations

import datetime as dt
import uuid

# Condition grading based on aggregated damage severity
GRADE_DESCRIPTIONS = {
    "A": "Excellent — no visible damage detected across all photos.",
    "B": "Good — only minor cosmetic issues detected.",
    "C": "Fair — moderate damage present; budget for repairs before purchase.",
    "D": "Poor — multiple moderate issues or a severe issue; negotiate accordingly.",
    "E": "Bad — severe structural/panel damage detected; professional inspection strongly advised.",
}

PURCHASE_LABELS = {
    "A": "Excellent Purchase", "B": "Good Purchase", "C": "Negotiate Price",
    "D": "High Risk", "E": "Avoid Buying",
}

EXPLANATION_TEMPLATES = {
    "minor": ("{part} shows minor surface damage (detection confidence {dc:.0%}). "
              "Classified minor because the affected area is small relative to the panel; "
              "typically cosmetic and repairable without part replacement."),
    "moderate": ("{part} shows moderate damage (detection confidence {dc:.0%}). "
                 "The affected area suggests panel work such as filler and repaint "
                 "rather than simple polishing."),
    "severe": ("{part} shows severe damage (detection confidence {dc:.0%}). "
               "The extent of deformation indicates the part likely needs replacement; "
               "inspect surrounding structure for hidden damage."),
}


def explain(damage: dict) -> str:
    return EXPLANATION_TEMPLATES.get(damage.get("severity", "moderate"), EXPLANATION_TEMPLATES["moderate"]).format(
        part=damage.get("damage_type", "Part"), dc=damage.get("detection_confidence", 0.0))


RECOMMENDATIONS = {
    "A": "Vehicle body appears clean. Standard mechanical inspection still recommended.",
    "B": "Cosmetic issues can be used to negotiate a small discount.",
    "C": "Request repair quotes and deduct the estimate from your offer.",
    "D": "Significant repair costs expected. Deduct the full high-end estimate from your offer, or walk away.",
    "E": "High risk purchase. Severe damage often hides structural issues a photo cannot show. An in-person professional inspection is essential before any payment.",
}


def compute_grade(all_damages: list[dict]) -> str:
    severe = sum(1 for d in all_damages if d["severity"] == "severe")
    moderate = sum(1 for d in all_damages if d["severity"] == "moderate")
    minor = sum(1 for d in all_damages if d["severity"] == "minor")
    if severe >= 2:
        return "E"
    if severe == 1 or moderate >= 3:
        return "D"
    if moderate >= 1:
        return "C"
    if minor >= 1:
        return "B"
    return "A"


def build_inspection_report(
    angle_results: list[dict],  # [{angle, damages, total_min, total_max, annotated_image}]
    extra_checks: list[dict] | None = None,
) -> dict:
    """Merge per-angle pipeline results into one professional report."""
    all_damages: list[dict] = []
    for r in angle_results:
        for d in r["damages"]:
            all_damages.append({**d, "angle": r["angle"]})

    total_min = sum(r["total_min"] for r in angle_results)
    total_max = sum(r["total_max"] for r in angle_results)
    grade = compute_grade(all_damages)

    parts_affected = sorted({d["damage_type"] for d in all_damages})
    for r in angle_results:
        for d in r["damages"]:
            d["explanation"] = explain(d)

    return {
        "report_id": uuid.uuid4().hex[:12].upper(),
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "photos_analyzed": len(angle_results),
        "condition_grade": grade,
        "condition_summary": GRADE_DESCRIPTIONS[grade],
        "purchase_recommendation": PURCHASE_LABELS[grade],
        "recommendation": RECOMMENDATIONS[grade],
        "damages_found": len(all_damages),
        "parts_affected": parts_affected,
        "estimated_repair_min": total_min,
        "estimated_repair_max": total_max,
        "currency": "USD",
        "angles": angle_results,
        "additional_checks": extra_checks or [
            {
                "check": "Prior repair / repaint detection",
                "status": "not_available",
                "note": "Coming soon — requires the repaint-detection model (roadmap).",
            }
        ],
        "disclaimer": (
            "This AI report covers externally visible body damage only. It cannot detect "
            "mechanical condition, frame damage, flood damage, or odometer fraud. "
            "Always verify the vehicle history report (VIN) and get an in-person "
            "professional inspection before purchase."
        ),
    }
