"""Damage assessment endpoint."""
import json

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from ..auth import enforce_quota, enforce_rate_limit, get_current_user
from ..database import get_db
from ..ml.cost_engine import vehicle_multiplier
from ..ml.pipeline import DamagePipeline
from ..models import Assessment, User
from ..schemas import AssessmentOut, DamageItem

router = APIRouter(prefix="/api/v1", tags=["assessment"])

MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB
ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp"}


@router.post("/assess", response_model=AssessmentOut)
async def assess_damage(
    file: UploadFile = File(..., description="Photo of the damaged vehicle (JPEG/PNG/WebP)"),
    confidence: float = Query(0.25, ge=0.05, le=0.9),
    include_images: bool = Query(True, description="Return annotated + Grad-CAM images (base64)"),
    vehicle_make: str = Query("", max_length=40),
    vehicle_model: str = Query("", max_length=60),
    vehicle_year: int = Query(0, ge=0, le=2030),
    country: str = Query("US", max_length=4, description="US|SA|AE|QA|KW|TR|YE|UK|EU"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    enforce_rate_limit(user)
    enforce_quota(db, user)

    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(415, f"Unsupported file type {file.content_type}. Use JPEG/PNG/WebP.")
    data = await file.read()
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "Image too large (max 10 MB)")

    pipeline = DamagePipeline.get()
    quality = "high" if user.plan in ("pro", "business") else "standard"
    mult = vehicle_multiplier(vehicle_make, vehicle_year, country)
    try:
        result = await run_in_threadpool(pipeline.assess, data, confidence, include_images, quality, mult)
    except ValueError as exc:
        raise HTTPException(422, str(exc))

    record = Assessment(
        user_id=user.id,
        vehicle_make=vehicle_make,
        vehicle_model=vehicle_model,
        vehicle_year=vehicle_year,
        num_damages=len(result.damages),
        total_min=result.total_min,
        total_max=result.total_max,
        inference_ms=result.inference_ms,
        result_json=json.dumps(result.damages),
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    return AssessmentOut(
        id=record.id,
        damages=[DamageItem(**d) for d in result.damages],
        total_min=result.total_min,
        total_max=result.total_max,
        inference_ms=result.inference_ms,
        annotated_image=result.annotated_image,
        gradcam_image=result.gradcam_image,
        warning=result.warning,
    )


@router.get("/assessments")
def list_assessments(
    limit: int = Query(20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(Assessment)
        .filter(Assessment.user_id == user.id)
        .order_by(Assessment.created_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": r.id,
            "created_at": r.created_at,
            "num_damages": r.num_damages,
            "total_min": r.total_min,
            "total_max": r.total_max,
            "inference_ms": r.inference_ms,
            "damages": json.loads(r.result_json or "[]"),
        }
        for r in rows
    ]
