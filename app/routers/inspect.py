"""Full-vehicle inspection endpoint (Pro+): multiple photos -> one condition report."""
import json

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from ..auth import enforce_quota, enforce_rate_limit, get_current_user, require_plan
from ..database import get_db
from ..ml.cost_engine import vehicle_multiplier
from ..ml.inspection import build_inspection_report
from ..ml.pipeline import DamagePipeline
from ..models import Assessment, User

router = APIRouter(prefix="/api/v1", tags=["inspection"])

ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_UPLOAD_BYTES = 10 * 1024 * 1024
MAX_PHOTOS = 8

ANGLE_NAMES = ["front", "front-left", "left", "rear-left", "rear",
               "rear-right", "right", "front-right"]


@router.post("/inspect")
async def inspect_vehicle(
    files: list[UploadFile] = File(..., description=f"2-{MAX_PHOTOS} photos covering the whole car"),
    confidence: float = Query(0.25, ge=0.05, le=0.9),
    vehicle_make: str = Query("", max_length=40),
    vehicle_model: str = Query("", max_length=60),
    vehicle_year: int = Query(0, ge=0, le=2030),
    country: str = Query("US", max_length=4, description="US|SA|AE|QA|KW|TR|YE|UK|EU"),
    include_images: bool = Query(True),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_plan(user, "pro")
    enforce_rate_limit(user)
    enforce_quota(db, user)

    if not 2 <= len(files) <= MAX_PHOTOS:
        raise HTTPException(400, f"Upload between 2 and {MAX_PHOTOS} photos of the vehicle.")

    pipeline = DamagePipeline.get()
    quality = "high"  # inspection is a paid feature -> always high-accuracy mode
    mult = vehicle_multiplier(vehicle_make, vehicle_year, country)
    angle_results = []

    for i, f in enumerate(files):
        if f.content_type not in ALLOWED_TYPES:
            raise HTTPException(415, f"File {i + 1}: unsupported type {f.content_type}")
        data = await f.read()
        if len(data) > MAX_UPLOAD_BYTES:
            raise HTTPException(413, f"File {i + 1}: too large (max 10 MB)")
        try:
            result = await run_in_threadpool(
                pipeline.assess, data, confidence, include_images, quality, mult
            )
        except ValueError as exc:
            raise HTTPException(422, f"File {i + 1}: {exc}")
        if result.warning:
            raise HTTPException(503, result.warning)
        angle_results.append({
            "angle": ANGLE_NAMES[i] if i < len(ANGLE_NAMES) else f"photo-{i + 1}",
            "damages": result.damages,
            "total_min": result.total_min,
            "total_max": result.total_max,
            "annotated_image": result.annotated_image,
        })

    report = build_inspection_report(angle_results)

    report["vehicle"] = {"make": vehicle_make, "model": vehicle_model, "year": vehicle_year}

    record = Assessment(
        user_id=user.id,
        vehicle_make=vehicle_make,
        vehicle_model=vehicle_model,
        vehicle_year=vehicle_year,
        num_damages=report["damages_found"],
        total_min=report["estimated_repair_min"],
        total_max=report["estimated_repair_max"],
        inference_ms=0.0,
        result_json=json.dumps({"type": "inspection", "report_id": report["report_id"],
                                "grade": report["condition_grade"]}),
    )
    db.add(record)
    db.commit()

    return report
