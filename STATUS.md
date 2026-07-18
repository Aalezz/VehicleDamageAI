# Suraya Car — Project Status

> Living document. The CTO (Claude) updates this each working session.
> To resume work in a new session: "Read STATUS.md and ROADMAP.md, then continue."

Last updated: 2026-07-18

## Current state

Production-ready FastAPI web app in this folder. All 12 tests pass
(`DEMO_MODE=true pytest tests/ -v`). Run locally:
`uvicorn app.main:app --reload` -> http://localhost:8000

Shipped: damage detection pipeline (needs trained weights), severity + costs
with parts/labor/paint breakdown, country pricing (US/SA/AE/QA/KW/TR/YE/UK/EU),
VIN decoder, multi-photo inspection with A-E grade + purchase recommendation,
PDF reports, explanations per finding, accounts/API keys/quotas, Stripe
subscription code (needs keys), free trial funnel, professional landing page.

## In flight

- [ ] MODEL TRAINING running in Colab (SurayaCar_Train_Colab.ipynb).
      When done: put yolov8_detector.pt + efficientnetv2.pth into models/,
      restart, verify /health shows "model_source": "trained".
      Record final metrics here: detector mAP@0.5 = ___ , severity acc = ___
- [ ] GitHub push (repo: github.com/Aalezz/VehicleDamageAI) — do via connected
      Chrome or git CLI.
- [ ] `pip install fpdf2 email-validator` in the local venv (new deps).

## Alezz's action list (human/account tasks)

1. Stripe account: dashboard.stripe.com -> connect bank -> create products
   Pro ($25/mo + $240/yr) and Business ($60/mo + $600/yr) -> put 4 price IDs,
   secret key, webhook secret in .env
2. Domain: buy surayacar.com (Namecheap or Cloudflare Registrar)
3. GPU host for launch: RunPod / Hetzner GPU / Lightning.ai account
4. Managed Postgres (Neon.tech or Supabase, free tier fine to start)
5. Object storage: Cloudflare R2 bucket (for uploaded photos, Phase 2)
6. START COLLECTING repaint-detection dataset: photos of repainted panels
   from body shops (label: which panel, repainted yes/no). This is the moat.
7. Rotate the Roboflow API key (was shown in a screenshot)

## Next sprint (when the above unblocks)

Sprint 1 — Launch hardening:
- Postgres migration + settings for production
- Tighten CORS + SECRET_KEY enforcement in prod mode
- Docker deploy on the GPU host, HTTPS via Caddy
- Stripe live-mode end-to-end test (checkout -> webhook -> plan upgrade)
- Smoke test with real photos + record model metrics

Sprint 2 — Value features (see ROADMAP.md Phase 2):
- Market value estimation (pricing source per region) -> "fair offer" math
- OCR document upload + summary
- Arabic + Turkish i18n
- Admin dashboard v1

## Decisions log

- 2026-07: SQLite for dev, Postgres for prod (env var switch already built)
- 2026-07: No fake AI ever — fallback mode refuses to output results (enforced)
- 2026-07: Severity labels derived from damage area (v1); human-labeled data
  planned for insurer-grade accuracy (Phase 3)
- 2026-07: Payments via Stripe; regional gateways deferred to Phase 2
