"""Authentication: bcrypt passwords, JWT sessions, API keys, plan quotas, rate limiting."""
import datetime as dt
import hashlib
import secrets
import threading
import time
from collections import defaultdict, deque

import bcrypt
import jwt
from fastapi import Depends, Header, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from .config import get_settings
from .database import get_db
from .models import ApiKey, Assessment, User

settings = get_settings()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), hashed.encode())
    except ValueError:
        return False


def create_access_token(user_id: int) -> str:
    payload = {
        "sub": str(user_id),
        "exp": dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=settings.access_token_expire_minutes),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> int | None:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
        return int(payload["sub"])
    except Exception:
        return None


def generate_api_key() -> tuple[str, str, str]:
    """Returns (raw_key, sha256_hash, prefix). Raw key shown to the user once."""
    raw = "vda_" + secrets.token_urlsafe(32)
    return raw, hashlib.sha256(raw.encode()).hexdigest(), raw[:12]


def lookup_api_key(db: Session, raw_key: str) -> User | None:
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    rec = db.query(ApiKey).filter(ApiKey.key_hash == key_hash, ApiKey.revoked_at.is_(None)).first()
    return rec.user if rec and rec.user.is_active else None


def get_current_user(
    token: str | None = Depends(oauth2_scheme),
    x_api_key: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> User:
    user: User | None = None
    if token:
        user_id = decode_token(token)
        if user_id is not None:
            user = db.get(User, user_id)
    if user is None and x_api_key:
        user = lookup_api_key(db, x_api_key)
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    return user


PLAN_QUOTAS = {
    "free": settings.free_monthly_quota,
    "pro": settings.pro_monthly_quota,
    "business": settings.business_monthly_quota,
}


def monthly_usage(db: Session, user: User) -> int:
    now = dt.datetime.now(dt.timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return (
        db.query(Assessment)
        .filter(Assessment.user_id == user.id, Assessment.created_at >= month_start)
        .count()
    )


def enforce_quota(db: Session, user: User) -> None:
    quota = PLAN_QUOTAS.get(user.plan, settings.free_monthly_quota)
    used = monthly_usage(db, user)
    if used >= quota:
        raise HTTPException(
            status.HTTP_402_PAYMENT_REQUIRED,
            f"Monthly quota reached ({used}/{quota}). Upgrade your plan to continue.",
        )


PLAN_RANK = {"free": 0, "pro": 1, "business": 2}


def require_plan(user: User, minimum: str) -> None:
    if PLAN_RANK.get(user.plan, 0) < PLAN_RANK[minimum]:
        raise HTTPException(
            status.HTTP_402_PAYMENT_REQUIRED,
            f"This feature requires the {minimum.capitalize()} plan. Upgrade to continue.",
        )


_rl_lock = threading.Lock()
_rl_hits: dict[int, deque] = defaultdict(deque)


def enforce_rate_limit(user: User) -> None:
    now = time.monotonic()
    window = 60.0
    with _rl_lock:
        hits = _rl_hits[user.id]
        while hits and now - hits[0] > window:
            hits.popleft()
        if len(hits) >= settings.rate_limit_per_minute:
            raise HTTPException(
                status.HTTP_429_TOO_MANY_REQUESTS,
                "Rate limit exceeded. Try again in a minute.",
            )
        hits.append(now)
