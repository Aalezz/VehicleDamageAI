"""Stripe billing: pricing info, checkout, webhook, customer portal.

Setup (one time, ~15 min):
1. Create a Stripe account at https://dashboard.stripe.com (payouts go to your bank).
2. Create a Product "VehicleDamageAI Pro" with 2 recurring prices:
   $25/month, and $240/year (= $20/mo billed annually).
   Create Product "VehicleDamageAI Business": $60/month, and $600/year (= $50/mo).
3. Put the 4 price IDs + secret key + webhook secret in .env.
4. Add a webhook endpoint in Stripe Dashboard pointing to
   https://YOUR_DOMAIN/api/v1/billing/webhook
   with events: checkout.session.completed, customer.subscription.updated,
   customer.subscription.deleted.
"""
import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..config import get_settings
from ..database import get_db
from ..models import User

logger = logging.getLogger(__name__)
settings = get_settings()
router = APIRouter(prefix="/api/v1/billing", tags=["billing"])


def _stripe():
    if not settings.stripe_secret_key:
        raise HTTPException(503, "Payments not configured yet. Set STRIPE_SECRET_KEY in .env.")
    try:
        import stripe
    except ImportError:
        raise HTTPException(503, "Stripe library not installed. Run: pip install stripe")
    stripe.api_key = settings.stripe_secret_key
    return stripe


PRICE_MAP_KEYS = {
    ("pro", "month"): "stripe_price_pro_monthly",
    ("pro", "year"): "stripe_price_pro_annual",
    ("business", "month"): "stripe_price_business_monthly",
    ("business", "year"): "stripe_price_business_annual",
}


@router.get("/plans")
def plans():
    """Public pricing table (used by the frontend)."""
    return {
        "currency": "USD",
        "plans": [
            {
                "id": "free", "name": "Free", "monthly": 0, "annual_per_month": 0,
                "quota": settings.free_monthly_quota,
                "features": ["Damage detection", "Cost estimates",
                             f"{settings.free_monthly_quota} assessments/month", "Standard accuracy"],
            },
            {
                "id": "pro", "name": "Pro",
                "monthly": settings.pro_price_monthly,
                "annual_per_month": settings.pro_price_annual_per_month,
                "quota": settings.pro_monthly_quota,
                "features": [f"{settings.pro_monthly_quota} assessments/month",
                             "High-accuracy mode (higher resolution + TTA)",
                             "Grad-CAM explainability",
                             "Full-vehicle inspection reports", "API access"],
            },
            {
                "id": "business", "name": "Business",
                "monthly": settings.business_price_monthly,
                "annual_per_month": settings.business_price_annual_per_month,
                "quota": settings.business_monthly_quota,
                "features": [f"{settings.business_monthly_quota:,} assessments/month",
                             "Everything in Pro", "Priority inference",
                             "Bulk/fleet inspections", "Priority support"],
            },
        ],
    }


@router.post("/checkout")
def create_checkout(plan: str, interval: str = "month",
                    user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if (plan, interval) not in PRICE_MAP_KEYS:
        raise HTTPException(400, "plan must be pro|business, interval month|year")
    price_id = getattr(settings, PRICE_MAP_KEYS[(plan, interval)])
    if not price_id:
        raise HTTPException(503, f"Price ID for {plan}/{interval} not configured in .env")

    stripe = _stripe()
    if not user.stripe_customer_id:
        customer = stripe.Customer.create(email=user.email, metadata={"user_id": user.id})
        user.stripe_customer_id = customer.id
        db.commit()

    session = stripe.checkout.Session.create(
        customer=user.stripe_customer_id,
        mode="subscription",
        line_items=[{"price": price_id, "quantity": 1}],
        success_url=f"{settings.public_base_url}/?upgraded=1",
        cancel_url=f"{settings.public_base_url}/?canceled=1",
        metadata={"user_id": user.id, "plan": plan, "interval": interval},
    )
    return {"checkout_url": session.url}


@router.post("/portal")
def customer_portal(user: User = Depends(get_current_user)):
    """Stripe-hosted portal: cancel/upgrade subscription, update card, invoices."""
    if not user.stripe_customer_id:
        raise HTTPException(400, "No billing account yet — subscribe to a plan first.")
    stripe = _stripe()
    session = stripe.billing_portal.Session.create(
        customer=user.stripe_customer_id,
        return_url=settings.public_base_url,
    )
    return {"portal_url": session.url}


@router.post("/webhook", include_in_schema=False)
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    stripe = _stripe()
    payload = await request.body()
    sig = request.headers.get("stripe-signature", "")
    try:
        event = stripe.Webhook.construct_event(payload, sig, settings.stripe_webhook_secret)
    except Exception:
        raise HTTPException(400, "Invalid webhook signature")

    obj = event["data"]["object"]

    if event["type"] == "checkout.session.completed":
        meta = obj.get("metadata", {})
        user = db.get(User, int(meta.get("user_id", 0)))
        if user:
            user.plan = meta.get("plan", "pro")
            user.billing_interval = meta.get("interval", "month")
            user.stripe_subscription_id = obj.get("subscription", "")
            db.commit()
            logger.info("User %s upgraded to %s (%s)", user.email, user.plan, user.billing_interval)

    elif event["type"] == "customer.subscription.deleted":
        user = db.query(User).filter(User.stripe_customer_id == obj.get("customer", "")).first()
        if user:
            user.plan = "free"
            user.billing_interval = ""
            user.stripe_subscription_id = ""
            db.commit()
            logger.info("User %s downgraded to free", user.email)

    return {"received": True}
