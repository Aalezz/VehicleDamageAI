"""Account endpoints: profile, usage, API key management."""
import datetime as dt

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..auth import PLAN_QUOTAS, generate_api_key, get_current_user, monthly_usage
from ..database import get_db
from ..models import ApiKey, User
from ..schemas import ApiKeyCreatedOut, ApiKeyCreateIn, ApiKeyOut, UsageOut, UserOut

router = APIRouter(prefix="/api/v1/account", tags=["account"])


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user


@router.get("/usage", response_model=UsageOut)
def usage(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    quota = PLAN_QUOTAS.get(user.plan, 0)
    used = monthly_usage(db, user)
    return UsageOut(plan=user.plan, monthly_quota=quota, used_this_month=used,
                    remaining=max(0, quota - used))


@router.get("/api-keys", response_model=list[ApiKeyOut])
def list_keys(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return (
        db.query(ApiKey)
        .filter(ApiKey.user_id == user.id, ApiKey.revoked_at.is_(None))
        .order_by(ApiKey.created_at.desc())
        .all()
    )


@router.post("/api-keys", response_model=ApiKeyCreatedOut, status_code=201)
def create_key(body: ApiKeyCreateIn, user: User = Depends(get_current_user),
               db: Session = Depends(get_db)):
    raw, key_hash, prefix = generate_api_key()
    rec = ApiKey(user_id=user.id, name=body.name, key_hash=key_hash, prefix=prefix)
    db.add(rec)
    db.commit()
    db.refresh(rec)
    return ApiKeyCreatedOut(id=rec.id, name=rec.name, prefix=rec.prefix,
                            created_at=rec.created_at, key=raw)


@router.delete("/api-keys/{key_id}", status_code=204)
def revoke_key(key_id: int, user: User = Depends(get_current_user),
               db: Session = Depends(get_db)):
    rec = db.query(ApiKey).filter(ApiKey.id == key_id, ApiKey.user_id == user.id).first()
    if not rec:
        raise HTTPException(404, "API key not found")
    rec.revoked_at = dt.datetime.now(dt.timezone.utc)
    db.commit()
