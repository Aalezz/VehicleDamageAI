"""VehicleDamageAI — production FastAPI application."""
import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .config import get_settings
from .database import Base, engine
from .routers import account, assess, auth_routes, billing, inspect, report, trial, vin

logging.basicConfig(level=logging.INFO)
settings = get_settings()

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Suraya Car API",
    version="2.1.0",
    description=(
        "AI-powered vehicle damage detection, severity classification and repair "
        "cost estimation. Authenticate with a bearer token (login) or `X-API-Key` header."
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_routes.router)
app.include_router(account.router)
app.include_router(assess.router)
app.include_router(billing.router)
app.include_router(inspect.router)
app.include_router(trial.router)
app.include_router(vin.router)
app.include_router(report.router)

STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/health", tags=["system"])
def health():
    from .ml.pipeline import DamagePipeline
    return {
        "status": "ok",
        "app": settings.app_name,
        "model_source": DamagePipeline.get().model_source,
        "demo_mode": settings.demo_mode,
    }
