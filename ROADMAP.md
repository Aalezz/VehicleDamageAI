# Suraya Car — Product Roadmap

Vision: the most accurate AI-powered vehicle inspection platform — a professional
mechanic and inspector in your pocket. Every prediction explained, every finding
with a confidence score, uncertain findings clearly labeled.

This roadmap orders the full product specification by what is buildable now,
what needs data collection, and what needs a team. Honest estimates included.

## Phase 1 — SHIPPED (current app)

- Exterior damage detection: 7 body zones (YOLOv8m, 82% mAP@0.5)
- Severity classification: minor/moderate/severe (EfficientNetV2-S, ~89%)
- Explainable AI: Grad-CAM heatmaps + per-finding written explanations
- Repair cost estimation with parts/labor/paint breakdown + repair time
- Country-specific pricing: US, SA, AE, QA, KW, TR, YE, UK, EU
- Vehicle-aware pricing (brand tier + age)
- VIN decoder (NHTSA vPIC — make/model/year/engine/transmission)
- Multi-photo full-vehicle inspection with A–E grade
- Purchase recommendation: Excellent Purchase → Avoid Buying
- Premium PDF report with annotated images
- Accounts (JWT), API keys, free trial (3 scans), Free/Pro/Business plans
- Stripe subscriptions (monthly + annual)
- Rate limiting, quotas, usage history

## Phase 2 — next 1–3 months (no new ML training needed)

- Market value estimation: integrate a pricing data source per region;
  report "market value − repairs = fair offer"
- OCR document upload: registration papers, invoices, reports (Tesseract/
  PaddleOCR) with automatic summary
- Postgres migration + S3/R2 media storage
- Admin dashboard: users, subscriptions, revenue, inspection stats
- Google login; email verification; password reset
- Arabic + Turkish translations (frontend is single-file; i18n is cheap)
- Regional payment gateways alongside side Stripe where needed

## Phase 3 — 3–9 months (needs data collection)

- Repaint / prior-repair detection: requires collecting a labeled dataset of
  repainted panels (paint texture, orange peel, color mismatch). Start
  collecting photos NOW from body shops — this is the moat feature.
- Fine-grained damage classes: scratches vs dents vs rust vs glass cracks
  (needs relabeled dataset with more classes)
- Interior inspection model (seat wear, dashboard, airbag flags) — new dataset
- Tire wear estimation from photos
- Human-labeled severity (replace area heuristic) for insurer-grade accuracy
- Model-specific known-issues database per make/model/year

## Phase 4 — 9–18 months (new modalities, small team)

- Engine audio AI: knocking/ticking/bearing/misfire classification.
  Needs thousands of labeled engine recordings — partner with workshops.
- Video walkaround analysis: frame sampling + detection merging + tracking
- OBD-II report ingestion and interpretation
- Live camera guidance ("move closer to the fender")
- iOS + Android apps (React Native wrapping the existing API)
- LLM-written report narratives

## Phase 5 — platform scale

- Kubernetes, autoscaling GPU inference, CDN, multi-region
- Dealer/fleet/enterprise plans, auction + marketplace integrations
- Insurance claim assessment product line
- AR damage overlays, predictive maintenance, voice assistant

## Principles (non-negotiable)

1. Never fake a capability. If a model isn't loaded or confident, the app says
   so (already enforced: fallback mode refuses to fabricate results).
2. Every prediction ships with a confidence score and an explanation.
3. Uncertain findings are labeled for manual verification, not hidden.
4. Marketing claims match measured metrics — publish the real numbers.
