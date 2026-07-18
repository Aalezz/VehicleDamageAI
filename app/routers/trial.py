"""Anonymous free trial: 3 assessments per visitor, no account needed.

Tracked per client IP in memory (resets on server restart - good enough for a
trial funnel; the frontend also tracks it in localStorage).
"""
import threading

from fastapi import APIRouter, File, HTTPException, Query, Request, UploadFile
from fastapi.concurrency import run_in_threadpool

from ..ml.cost_engine import vehicle_multiplier
from ..ml.pipeline import DamagePipeline

router = APIRouter(prefix="/api/v1/trial", tags=["trial"])

TRIAL_LIMIT = 3
ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_UPLOAD_BYTES = 10 * 1024 * 1024

_lock = threading.Lock()
_trials: dict[str, int] = {}


def _client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for")
    return (fwd.split(",")[0].strip() if fwd else request.client.host) or "unknown"


@router.get("/remaining")
def remaining(request: Request):
    used = _trials.get(_client_ip(request), 0)
    return {"limit": TRIAL_LIMIT, "used": used, "remaining": max(0, TRIAL_LIMIT - used)}


@router.post("/assess")
async def trial_assess(
    request: Request,
    file: UploadFile = File(...),
    vehicle_make: str = Query("", max_length=40),
    vehicle_model: str = Query("", max_length=60),
    vehicle_year: int = Query(0, ge=0, le=2030),
    country: str = Query("US", max_length=4, description="US|SA|AE|QA|KW|TR|YE|UK|EU"),
):
    ip = _client_ip(request)
    with _lock:
        used = _trials.get(ip, 0)
        if used >= TRIAL_LIMIT:
            raise HTTPException(
                402, "Free trial finished (3/3 used). Create a free account to continue."
            )
        _trials[ip] = used + 1

    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(415, f"Unsupported file type {file.content_type}.")
    data = await file.read()
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "Image too large (max 10 MB)")

    pipeline = DamagePipeline.get()
    mult = vehicle_multiplier(vehicle_make, vehicle_year, country)
    try:
        result = await run_in_threadpool(
            pipeline.assess, data, None, True, "standard", mult
        )
    except ValueError as exc:
        raise HTTPException(422, str(exc))

    return {
        "damages": result.damages,
        "total_min": result.total_min,
        "total_max": result.total_max,
        "currency": "USD",
        "inference_ms": result.inference_ms,
        "annotated_image": result.annotated_image,
        "warning": result.warning,
        "vehicle": {"make": vehicle_make, "model": vehicle_model, "year": vehicle_year},
        "trial_remaining": TRIAL_LIMIT - _trials[ip],
        "disclaimer": "Trial mode. Create a free account for Grad-CAM, history and API access.",
    }
