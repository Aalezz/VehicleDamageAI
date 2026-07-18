# 🚗 Suraya Car (VehicleDamageAI)

> **AI-powered vehicle damage detection, severity classification & repair cost estimation — now a full production web app.**

[![Python](https://img.shields.io/badge/Python-3.10+-blue?logo=python)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111+-009688?logo=fastapi)](https://fastapi.tiangolo.com)
[![PyTorch](https://img.shields.io/badge/PyTorch-2.3-red?logo=pytorch)](https://pytorch.org)
[![YOLOv8](https://img.shields.io/badge/YOLOv8-Ultralytics-brightgreen)](https://ultralytics.com)
[![License](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)

Upload a photo of a damaged vehicle and get, in under a second:

1. **Where** the damage is and which part is affected (YOLOv8m)
2. **How severe** it is — minor / moderate / severe (EfficientNetV2-S)
3. **Why** the model decided that (Grad-CAM heatmaps)
4. **How much** the repair will cost (rule-based cost engine)

## What's in v2.0

The original Colab research pipeline is now a sellable, multi-user web product:

| Capability | Details |
|---|---|
| REST API | FastAPI, OpenAPI docs at `/docs` |
| Web app | Polished single-page frontend at `/` — upload, results, dashboard |
| Accounts | Email + password registration, JWT sessions |
| API keys | Per-user keys (`X-API-Key` header) for programmatic access |
| Plans & quotas | Free / Pro / Business monthly quotas, enforced server-side |
| Rate limiting | Per-user sliding window (default 20 req/min) |
| Usage history | Every assessment stored and queryable |
| Deployment | Dockerfile + docker-compose, SQLite → Postgres via one env var |
| Tests | `pytest` suite that runs without GPU (`DEMO_MODE=true`) |

## Quick start

```bash
git clone https://github.com/Aalezz/VehicleDamageAI.git
cd VehicleDamageAI

python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env      # set SECRET_KEY!

# Place your trained weights (optional but recommended):
#   models/yolov8_detector.pt
#   models/efficientnetv2.pth
# Without them the app falls back to a pretrained detector so it still runs.

uvicorn app.main:app --reload
```

Open **http://localhost:8000** for the web app, **http://localhost:8000/docs** for the API.

### Docker

```bash
cp .env.example .env      # edit SECRET_KEY
docker compose up --build
```

## API usage

```bash
# Register + login
curl -X POST localhost:8000/api/v1/auth/register \
  -H 'Content-Type: application/json' \
  -d '{"email":"you@example.com","password":"yourpassword1"}'

TOKEN=$(curl -s -X POST localhost:8000/api/v1/auth/login \
  -d 'username=you@example.com&password=yourpassword1' | jq -r .access_token)

# Assess a photo
curl -X POST 'localhost:8000/api/v1/assess?confidence=0.25' \
  -H "Authorization: Bearer $TOKEN" \
  -F 'file=@car_damage.jpg'
```

Response (truncated):

```json
{
  "damages": [
    {"damage_type": "Door", "severity": "moderate",
     "detection_confidence": 0.91, "severity_confidence": 0.87,
     "repair": "Body filler + repaint", "cost_min": 500, "cost_max": 1200,
     "box": [120, 200, 420, 480]}
  ],
  "total_min": 500, "total_max": 1200, "currency": "USD",
  "inference_ms": 240.5,
  "annotated_image": "<base64 JPEG>", "gradcam_image": "<base64 JPEG>"
}
```

Or create an API key in the dashboard and call with `-H "X-API-Key: vda_..."`.

## Architecture

```
Photo ──► YOLOv8m detector ──► crop regions ──► EfficientNetV2-S severity
                │                                      │
                ▼                                      ▼
         annotated image                        Grad-CAM heatmap
                └──────────────┬───────────────────────┘
                               ▼
                     Cost engine ──► JSON report ($ min–max)
```

- **Damage classes (7):** Bonnet, Bumper, Dickey, Door, Fender, Light, Windshield
- **Severity:** minor 🟢 / moderate 🟡 / severe 🔴
- **Performance:** YOLOv8m mAP@0.5 ≈ 0.82 · classifier val acc ≈ 89% · < 0.3 s/image on GPU

## Training

The full training pipeline lives in [`notebooks/VehicleDamageAI_Colab.ipynb`](notebooks/VehicleDamageAI_Colab.ipynb) (Google Colab, ~45 min on a T4). It exports the two weight files the app consumes.

## Scaling to 1,000+ users

- Switch to Postgres: `DATABASE_URL=postgresql+psycopg2://...`
- Run 1 uvicorn worker per GPU; add replicas behind nginx/Traefik
- GPU strongly recommended (~0.3 s/image vs several seconds on CPU)
- Rate limits and monthly quotas are already enforced per user
- For billing, wire the Stripe env vars and add a checkout webhook (schema is plan-ready: `users.plan`)

## Project structure

```
app/
├── main.py              # FastAPI app
├── config.py            # env-based settings
├── auth.py              # JWT, API keys, quotas, rate limiting
├── database.py, models.py, schemas.py
├── routers/             # auth, account, assess
├── ml/
│   ├── pipeline.py      # 2-stage inference (lazy-loaded, thread-safe)
│   └── cost_engine.py   # repair cost rules
└── static/index.html    # web frontend
tests/test_api.py        # runs without GPU (DEMO_MODE)
Dockerfile, docker-compose.yml
```

## Tests

```bash
DEMO_MODE=true pytest tests/ -v
```

## License

MIT — see [LICENSE](LICENSE).

## Disclaimer

Cost estimates are indicative only, based on US average repair pricing. Actual costs vary by location, vehicle make/model, and repair shop.
