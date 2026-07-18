"""Application configuration via environment variables (.env supported)."""
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    # --- General ---
    app_name: str = "VehicleDamageAI"
    debug: bool = False

    # --- Security ---
    secret_key: str = "CHANGE_ME_use_a_long_random_string"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24  # 24h

    # --- Database ---
    database_url: str = f"sqlite:///{BASE_DIR / 'vehicledamage.db'}"

    # --- ML models ---
    models_dir: Path = BASE_DIR / "models"
    detector_weights: str = "yolov8_detector.pt"
    classifier_weights: str = "efficientnetv2.pth"
    detector_fallback: str = "yolov8n.pt"
    default_confidence: float = 0.25
    enable_gradcam: bool = True
    demo_mode: bool = False

    # --- Plans & quotas (assessments per calendar month) ---
    free_monthly_quota: int = 15
    pro_monthly_quota: int = 500
    business_monthly_quota: int = 10000

    # --- Pricing (USD) ---
    pro_price_monthly: int = 25
    pro_price_annual_per_month: int = 20
    business_price_monthly: int = 60
    business_price_annual_per_month: int = 50

    # --- Rate limiting ---
    rate_limit_per_minute: int = 20

    # --- Stripe (money goes to YOUR Stripe account) ---
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_price_pro_monthly: str = ""
    stripe_price_pro_annual: str = ""
    stripe_price_business_monthly: str = ""
    stripe_price_business_annual: str = ""
    public_base_url: str = "http://localhost:8000"

    class Config:
        env_file = ".env"
        extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    return Settings()
