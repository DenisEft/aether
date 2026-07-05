"""Seed subscription plans for Aether platform.

Run once to initialize default plans: Free, Starter, Pro, Enterprise.
"""

from __future__ import annotations

import asyncio
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.billing import SubscriptionPlan

logger = logging.getLogger("aether.seeds.plans")

DEFAULT_PLANS = [
    {
        "id": "free",
        "name": "Free",
        "description": "For individuals and small projects. No credit card required.",
        "price_monthly_usd": 0.0,
        "price_yearly_usd": 0.0,
        "features": [
            "1 AI model (basic)",
            "1,000 messages/month",
            "Web widget",
            "Email channel",
            "Basic analytics",
            "Community support",
        ],
        "limits": {
            "max_tokens_per_month": 50_000,
            "max_conversations_per_month": 100,
            "max_documents_per_month": 50,
            "max_users": 1,
            "max_channels": 2,
        },
        "is_public": True,
        "sort_order": 0,
    },
    {
        "id": "starter",
        "name": "Starter",
        "description": "For growing teams. More power, more channels.",
        "price_monthly_usd": 29.0,
        "price_yearly_usd": 290.0,
        "features": [
            "3 AI models",
            "10,000 messages/month",
            "All channels (Telegram, WhatsApp, Email, Widget)",
            "Document AI (templates + extraction)",
            "5 users",
            "Advanced analytics",
            "Email support",
        ],
        "limits": {
            "max_tokens_per_month": 250_000,
            "max_conversations_per_month": 500,
            "max_documents_per_month": 200,
            "max_users": 5,
            "max_channels": 5,
        },
        "is_public": True,
        "sort_order": 1,
    },
    {
        "id": "pro",
        "name": "Pro",
        "description": "For businesses. Full AI power, unlimited channels.",
        "price_monthly_usd": 99.0,
        "price_yearly_usd": 990.0,
        "features": [
            "All AI models + custom models",
            "Unlimited messages",
            "Full Document AI pipeline",
            "20 users",
            "Priority AI queue",
            "Custom plugins",
            "API access",
            "Priority support",
        ],
        "limits": {
            "max_tokens_per_month": 1_000_000,
            "max_conversations_per_month": 2_000,
            "max_documents_per_month": 1_000,
            "max_users": 20,
            "max_channels": 10,
        },
        "is_public": True,
        "sort_order": 2,
    },
    {
        "id": "enterprise",
        "name": "Enterprise",
        "description": "For large organizations. White-label, on-prem, dedicated support.",
        "price_monthly_usd": 499.0,
        "price_yearly_usd": 4_990.0,
        "features": [
            "Everything in Pro",
            "Unlimited users",
            "White-label (full)",
            "On-premise deploy",
            "SSO (OIDC/SAML)",
            "Dedicated support",
            "SLA 99.9%",
            "Custom integrations",
            "Dedicated inference pool",
        ],
        "limits": {
            "max_tokens_per_month": 10_000_000,
            "max_conversations_per_month": 50_000,
            "max_documents_per_month": 10_000,
            "max_users": 999,
            "max_channels": 999,
        },
        "is_public": True,
        "sort_order": 3,
    },
]


async def seed_plans(session: AsyncSession) -> int:
    """Insert default plans if they don't exist. Returns count of created plans."""
    created = 0
    for plan_data in DEFAULT_PLANS:
        existing = await session.execute(
            select(SubscriptionPlan).where(SubscriptionPlan.id == plan_data["id"])
        )
        if existing.scalar_one_or_none() is not None:
            logger.debug(f"Plan {plan_data['id']} already exists, skipping")
            continue

        plan = SubscriptionPlan(**plan_data)
        session.add(plan)
        created += 1
        logger.info(f"Created plan: {plan_data['id']} ({plan_data['name']})")

    if created > 0:
        await session.commit()
        logger.info(f"Seeded {created} subscription plans")

    return created


async def seed_plans_command():
    """CLI entrypoint for seeding plans."""
    from app.core.database import async_session_factory

    async with async_session_factory() as session:
        created = await seed_plans(session)
        if created == 0:
            print("All plans already exist.")
        else:
            print(f"Created {created} plans.")


if __name__ == "__main__":
    asyncio.run(seed_plans_command())
