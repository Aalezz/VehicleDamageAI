"""API tests. Run with DEMO_MODE=true so no ML dependencies are needed:

    DEMO_MODE=true pytest tests/ -v
"""
import os

os.environ["DEMO_MODE"] = "true"
os.environ["DATABASE_URL"] = "sqlite:///./test.db"

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

EMAIL = "test@example.com"
PASSWORD = "supersecret123"


@pytest.fixture(scope="module")
def token():
    client.post("/api/v1/auth/register", json={"email": EMAIL, "password": PASSWORD})
    r = client.post("/api/v1/auth/login", data={"username": EMAIL, "password": PASSWORD})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def _fake_jpeg() -> bytes:
    return b"\xff\xd8\xff\xe0" + b"\x00" * 128 + b"\xff\xd9"


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_register_duplicate():
    client.post("/api/v1/auth/register", json={"email": EMAIL, "password": PASSWORD})
    r = client.post("/api/v1/auth/register", json={"email": EMAIL, "password": PASSWORD})
    assert r.status_code == 409


def test_login_wrong_password():
    r = client.post("/api/v1/auth/login", data={"username": EMAIL, "password": "wrong"})
    assert r.status_code == 401


def test_assess_requires_auth():
    r = client.post("/api/v1/assess", files={"file": ("car.jpg", _fake_jpeg(), "image/jpeg")})
    assert r.status_code == 401


def test_assess_demo(token):
    r = client.post(
        "/api/v1/assess",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("car.jpg", _fake_jpeg(), "image/jpeg")},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["damages"], "demo mode should return mock damages"
    assert body["total_max"] >= body["total_min"] > 0


def test_assess_rejects_bad_type(token):
    r = client.post(
        "/api/v1/assess",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("car.gif", b"GIF89a", "image/gif")},
    )
    assert r.status_code == 415


def test_usage_and_history(token):
    h = {"Authorization": f"Bearer {token}"}
    u = client.get("/api/v1/account/usage", headers=h).json()
    assert u["used_this_month"] >= 1
    hist = client.get("/api/v1/assessments", headers=h).json()
    assert len(hist) >= 1


def test_pricing_public():
    r = client.get("/api/v1/billing/plans")
    assert r.status_code == 200
    plans = {p["id"]: p for p in r.json()["plans"]}
    assert plans["pro"]["monthly"] == 25 and plans["pro"]["annual_per_month"] == 20
    assert plans["business"]["monthly"] == 60 and plans["business"]["annual_per_month"] == 50


def test_checkout_unconfigured(token):
    r = client.post("/api/v1/billing/checkout?plan=pro&interval=month",
                    headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 503


def test_inspect_requires_pro(token):
    files = [("files", ("a.jpg", _fake_jpeg(), "image/jpeg")),
             ("files", ("b.jpg", _fake_jpeg(), "image/jpeg"))]
    r = client.post("/api/v1/inspect", headers={"Authorization": f"Bearer {token}"}, files=files)
    assert r.status_code == 402


def test_inspect_as_pro(token):
    from app.database import SessionLocal
    from app.models import User
    db = SessionLocal()
    u = db.query(User).filter(User.email == EMAIL).first()
    u.plan = "pro"
    db.commit()
    db.close()

    files = [("files", ("a.jpg", _fake_jpeg(), "image/jpeg")),
             ("files", ("b.jpg", _fake_jpeg(), "image/jpeg"))]
    r = client.post("/api/v1/inspect", headers={"Authorization": f"Bearer {token}"}, files=files)
    assert r.status_code == 200, r.text
    rep = r.json()
    assert rep["condition_grade"] in "ABCDE"
    assert rep["photos_analyzed"] == 2
    assert "recommendation" in rep and "disclaimer" in rep


def test_api_key_flow(token):
    h = {"Authorization": f"Bearer {token}"}
    created = client.post("/api/v1/account/api-keys", json={"name": "ci"}, headers=h)
    assert created.status_code == 201
    raw_key = created.json()["key"]
    assert raw_key.startswith("vda_")

    r = client.post(
        "/api/v1/assess",
        headers={"X-API-Key": raw_key},
        files={"file": ("car.jpg", _fake_jpeg(), "image/jpeg")},
    )
    assert r.status_code == 200

    key_id = created.json()["id"]
    assert client.delete(f"/api/v1/account/api-keys/{key_id}", headers=h).status_code == 204
    r = client.post(
        "/api/v1/assess",
        headers={"X-API-Key": raw_key},
        files={"file": ("car.jpg", _fake_jpeg(), "image/jpeg")},
    )
    assert r.status_code == 401
