"""Billing endpoints: plans, subscriptions, invoices, usage, payment methods."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, date

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select, func

from app.core.deps import DBDep, CurrentActiveUser, CurrentSuperuser
from app.models.billing import (
    Invoice,
    PaymentMethod,
    Subscription,
    SubscriptionPlan,
    UsageRecord,
)
from app.models.enums import SubscriptionStatus, InvoiceStatus
from app.schemas.billing import (
    InvoiceCreate,
    InvoiceResponse,
    InvoiceUpdate,
    PaymentMethodCreate,
    PaymentMethodResponse,
    PaymentMethodUpdate,
    SubscriptionCreate,
    SubscriptionPlanCreate,
    SubscriptionPlanResponse,
    SubscriptionPlanUpdate,
    SubscriptionResponse,
    SubscriptionUpdate,
    UsageRecordCreate,
    UsageRecordResponse,
    UsageSummaryResponse,
)

router = APIRouter(tags=["billing"])


# ─────────────────────────────────────────────────────────────
# SUBSCRIPTION PLANS (global — superuser manages, active user reads)
# ─────────────────────────────────────────────────────────────

@router.get("/billing/plans", response_model=list[SubscriptionPlanResponse])
async def list_plans(
    db: DBDep,
    current_user: CurrentActiveUser,
    is_public: bool | None = Query(None),
) -> list[SubscriptionPlanResponse]:
    """List subscription plans. Public plans + all for superuser."""
    stmt = select(SubscriptionPlan)
    if is_public is not None:
        stmt = stmt.where(SubscriptionPlan.is_public == is_public)
    stmt = stmt.order_by(SubscriptionPlan.sort_order, SubscriptionPlan.name)
    result = await db.execute(stmt)
    return [SubscriptionPlanResponse.model_validate(p) for p in result.scalars().all()]


@router.post("/billing/plans", response_model=SubscriptionPlanResponse, status_code=201)
async def create_plan(
    body: SubscriptionPlanCreate,
    db: DBDep,
    current_user: CurrentSuperuser,
) -> SubscriptionPlanResponse:
    """Create a new subscription plan (superuser only)."""
    plan = SubscriptionPlan(
        id=body.id,
        name=body.name,
        description=body.description,
        price_monthly_usd=body.price_monthly_usd,
        price_yearly_usd=body.price_yearly_usd,
        features=body.features,
        limits=body.limits,
        is_public=body.is_public,
        sort_order=body.sort_order,
    )
    db.add(plan)
    await db.commit()
    await db.refresh(plan)
    return SubscriptionPlanResponse.model_validate(plan)


@router.get("/billing/plans/{plan_id}", response_model=SubscriptionPlanResponse)
async def get_plan(
    plan_id: str,
    db: DBDep,
    current_user: CurrentActiveUser,
) -> SubscriptionPlanResponse:
    """Get subscription plan details."""
    result = await db.execute(
        select(SubscriptionPlan).where(SubscriptionPlan.id == plan_id)
    )
    plan = result.scalar_one_or_none()
    if plan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found")
    return SubscriptionPlanResponse.model_validate(plan)


@router.patch("/billing/plans/{plan_id}", response_model=SubscriptionPlanResponse)
async def update_plan(
    plan_id: str,
    body: SubscriptionPlanUpdate,
    db: DBDep,
    current_user: CurrentSuperuser,
) -> SubscriptionPlanResponse:
    """Update a subscription plan (superuser only)."""
    result = await db.execute(
        select(SubscriptionPlan).where(SubscriptionPlan.id == plan_id)
    )
    plan = result.scalar_one_or_none()
    if plan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found")

    for field in ("name", "description", "price_monthly_usd", "price_yearly_usd",
                  "features", "limits", "is_public", "sort_order"):
        val = getattr(body, field, None)
        if val is not None:
            setattr(plan, field, val)

    await db.commit()
    await db.refresh(plan)
    return SubscriptionPlanResponse.model_validate(plan)


@router.delete("/billing/plans/{plan_id}", status_code=200)
async def delete_plan(
    plan_id: str,
    db: DBDep,
    current_user: CurrentSuperuser,
) -> dict:
    """Delete a subscription plan (superuser only)."""
    result = await db.execute(
        select(SubscriptionPlan).where(SubscriptionPlan.id == plan_id)
    )
    plan = result.scalar_one_or_none()
    if plan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found")

    await db.delete(plan)
    await db.commit()
    return {"message": "Plan deleted"}


# ─────────────────────────────────────────────────────────────
# SUBSCRIPTIONS (tenant-scoped)
# ─────────────────────────────────────────────────────────────

@router.get("/billing/subscriptions", response_model=list[SubscriptionResponse])
async def list_subscriptions(
    db: DBDep,
    current_user: CurrentActiveUser,
) -> list[SubscriptionResponse]:
    """List subscriptions for the current tenant."""
    result = await db.execute(
        select(Subscription)
        .where(Subscription.tenant_id == current_user.tenant_id)
        .order_by(Subscription.created_at.desc())
    )
    return [SubscriptionResponse.model_validate(s) for s in result.scalars().all()]


@router.post("/billing/subscriptions", response_model=SubscriptionResponse, status_code=201)
async def create_subscription(
    body: SubscriptionCreate,
    db: DBDep,
    current_user: CurrentActiveUser,
) -> SubscriptionResponse:
    """Subscribe to a plan."""
    # Verify plan exists
    plan_result = await db.execute(
        select(SubscriptionPlan).where(SubscriptionPlan.id == body.plan_id)
    )
    plan = plan_result.scalar_one_or_none()
    if plan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found")

    now = datetime.utcnow()
    trial_started = None
    trial_ends = None
    status = SubscriptionStatus.active

    if body.trial_days:
        trial_started = now
        trial_ends = now + timedelta(days=body.trial_days)
        status = SubscriptionStatus.trial

    sub = Subscription(
        tenant_id=current_user.tenant_id,
        plan_id=body.plan_id,
        status=status,
        trial_started_at=trial_started,
        trial_ends_at=trial_ends,
        current_period_start=now,
        current_period_end=now + timedelta(days=30),
    )
    db.add(sub)
    await db.commit()
    await db.refresh(sub)
    return SubscriptionResponse.model_validate(sub)


@router.get("/billing/subscriptions/{subscription_id}", response_model=SubscriptionResponse)
async def get_subscription(
    subscription_id: uuid.UUID,
    db: DBDep,
    current_user: CurrentActiveUser,
) -> SubscriptionResponse:
    """Get subscription details."""
    result = await db.execute(
        select(Subscription).where(
            Subscription.id == subscription_id,
            Subscription.tenant_id == current_user.tenant_id,
        )
    )
    sub = result.scalar_one_or_none()
    if sub is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subscription not found")
    return SubscriptionResponse.model_validate(sub)


@router.patch("/billing/subscriptions/{subscription_id}", response_model=SubscriptionResponse)
async def update_subscription(
    subscription_id: uuid.UUID,
    body: SubscriptionUpdate,
    db: DBDep,
    current_user: CurrentActiveUser,
) -> SubscriptionResponse:
    """Update a subscription."""
    result = await db.execute(
        select(Subscription).where(
            Subscription.id == subscription_id,
            Subscription.tenant_id == current_user.tenant_id,
        )
    )
    sub = result.scalar_one_or_none()
    if sub is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subscription not found")

    if body.plan_id is not None:
        sub.plan_id = body.plan_id
    if body.status is not None:
        sub.status = body.status
    if body.auto_renew is not None:
        sub.auto_renew = body.auto_renew
    if body.payment_method_id is not None:
        sub.payment_method_id = body.payment_method_id

    await db.commit()
    await db.refresh(sub)
    return SubscriptionResponse.model_validate(sub)


@router.delete("/billing/subscriptions/{subscription_id}", status_code=200)
async def cancel_subscription(
    subscription_id: uuid.UUID,
    db: DBDep,
    current_user: CurrentActiveUser,
) -> dict:
    """Cancel a subscription."""
    result = await db.execute(
        select(Subscription).where(
            Subscription.id == subscription_id,
            Subscription.tenant_id == current_user.tenant_id,
        )
    )
    sub = result.scalar_one_or_none()
    if sub is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subscription not found")

    sub.status = SubscriptionStatus.cancelled
    await db.commit()
    return {"message": "Subscription cancelled"}


# ─────────────────────────────────────────────────────────────
# INVOICES (tenant-scoped)
# ─────────────────────────────────────────────────────────────

@router.get("/billing/invoices", response_model=list[InvoiceResponse])
async def list_invoices(
    db: DBDep,
    current_user: CurrentActiveUser,
    status: InvoiceStatus | None = Query(None),
) -> list[InvoiceResponse]:
    """List invoices for the current tenant."""
    stmt = select(Invoice).where(Invoice.tenant_id == current_user.tenant_id)
    if status is not None:
        stmt = stmt.where(Invoice.status == status)
    stmt = stmt.order_by(Invoice.created_at.desc())
    result = await db.execute(stmt)
    return [InvoiceResponse.model_validate(i) for i in result.scalars().all()]


@router.get("/billing/invoices/{invoice_id}", response_model=InvoiceResponse)
async def get_invoice(
    invoice_id: uuid.UUID,
    db: DBDep,
    current_user: CurrentActiveUser,
) -> InvoiceResponse:
    """Get invoice details."""
    result = await db.execute(
        select(Invoice).where(
            Invoice.id == invoice_id,
            Invoice.tenant_id == current_user.tenant_id,
        )
    )
    invoice = result.scalar_one_or_none()
    if invoice is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")
    return InvoiceResponse.model_validate(invoice)


# ─────────────────────────────────────────────────────────────
# USAGE RECORDS (tenant-scoped)
# ─────────────────────────────────────────────────────────────

@router.get("/billing/usage", response_model=list[UsageRecordResponse])
async def list_usage(
    db: DBDep,
    current_user: CurrentActiveUser,
    metric: str | None = Query(None),
    limit: int = Query(default=100, le=1000),
) -> list[UsageRecordResponse]:
    """List usage records for the current tenant."""
    stmt = select(UsageRecord).where(UsageRecord.tenant_id == current_user.tenant_id)
    if metric is not None:
        stmt = stmt.where(UsageRecord.metric == metric)
    stmt = stmt.order_by(UsageRecord.recorded_at.desc()).limit(limit)
    result = await db.execute(stmt)
    return [UsageRecordResponse.model_validate(u) for u in result.scalars().all()]


@router.post("/billing/usage", response_model=UsageRecordResponse, status_code=201)
async def record_usage(
    body: UsageRecordCreate,
    db: DBDep,
    current_user: CurrentActiveUser,
) -> UsageRecordResponse:
    """Record a usage metric."""
    usage = UsageRecord(
        tenant_id=current_user.tenant_id,
        metric=body.metric,
        value=body.value,
        period=body.period,
    )
    db.add(usage)
    await db.commit()
    await db.refresh(usage)
    return UsageRecordResponse.model_validate(usage)


@router.get("/billing/usage/summary", response_model=UsageSummaryResponse)
async def usage_summary(
    db: DBDep,
    current_user: CurrentActiveUser,
    metric: str = Query(...),
) -> UsageSummaryResponse:
    """Get usage summary for a metric."""
    result = await db.execute(
        select(
            func.sum(UsageRecord.value),
            func.count(UsageRecord.id),
            func.max(UsageRecord.recorded_at),
        ).where(
            UsageRecord.tenant_id == current_user.tenant_id,
            UsageRecord.metric == metric,
        )
    )
    total, count, latest = result.one()
    return UsageSummaryResponse(
        tenant_id=current_user.tenant_id,
        metric=metric,
        period="total",
        total=float(total or 0),
        count=count or 0,
        recorded_at=latest or datetime.utcnow(),
    )
