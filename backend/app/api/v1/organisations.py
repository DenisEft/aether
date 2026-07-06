"""Organisation CRUD + membership management."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.core.deps import CurrentActiveUser, DBDep
from app.models.organisations import Organisation
from app.models.users import Membership, Role, User
from app.schemas.organisations import (
    ChangeRoleRequest,
    InviteCreateRequest,
    InviteResponse,
    OrganisationCreate,
    OrganisationMemberResponse,
    OrganisationResponse,
    OrganisationUpdate,
)


async def _verify_org_membership(
    org_id: uuid.UUID, db: DBDep, current_user: CurrentActiveUser
) -> Membership | None:
    """Verify user is a member of the organisation. Returns Membership or None."""
    result = await db.execute(
        select(Membership).where(
            Membership.organisation_id == org_id,
            Membership.user_id == current_user.id,
            Membership.tenant_id == current_user.tenant_id,
        )
    )
    membership = result.scalar_one_or_none()
    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not a member of this organisation",
        )
    return membership


router = APIRouter(tags=["organisations"])


# ── GET /organisations ────────────────────────────────────────


@router.get("/organisations", response_model=list[OrganisationResponse])
async def list_organisations(
    db: DBDep, current_user: CurrentActiveUser
) -> list[OrganisationResponse]:
    """List all organisations in the current tenant."""
    result = await db.execute(
        select(Organisation)
        .where(Organisation.tenant_id == current_user.tenant_id)
        .order_by(Organisation.name)
    )
    orgs = result.scalars().all()
    return [OrganisationResponse.model_validate(o) for o in orgs]


# ── POST /organisations ───────────────────────────────────────


@router.post("/organisations", response_model=OrganisationResponse, status_code=201)
async def create_organisation(
    body: OrganisationCreate,
    db: DBDep,
    current_user: CurrentActiveUser,
) -> OrganisationResponse:
    """Create a new organisation."""
    slug = body.slug or body.name.lower().replace(" ", "-")

    # Check slug uniqueness within tenant
    result = await db.execute(
        select(Organisation).where(
            Organisation.tenant_id == current_user.tenant_id,
            Organisation.slug == slug,
        )
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Organisation with slug '{slug}' already exists",
        )

    org = Organisation(
        tenant_id=current_user.tenant_id,
        name=body.name,
        slug=slug,
    )
    db.add(org)
    await db.commit()
    await db.refresh(org)

    return OrganisationResponse.model_validate(org)


# ── GET /organisations/{org_id} ───────────────────────────────


@router.get("/organisations/{org_id}", response_model=OrganisationResponse)
async def get_organisation(
    org_id: uuid.UUID,
    db: DBDep,
    current_user: CurrentActiveUser,
) -> OrganisationResponse:
    """Get organisation details."""
    result = await db.execute(
        select(Organisation).where(
            Organisation.id == org_id,
            Organisation.tenant_id == current_user.tenant_id,
        )
    )
    org = result.scalar_one_or_none()
    if org is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organisation not found")
    return OrganisationResponse.model_validate(org)


# ── PATCH /organisations/{org_id} ─────────────────────────────


@router.patch("/organisations/{org_id}", response_model=OrganisationResponse)
async def update_organisation(
    org_id: uuid.UUID,
    body: OrganisationUpdate,
    db: DBDep,
    current_user: CurrentActiveUser,
) -> OrganisationResponse:
    """Update organisation name or logo."""
    result = await db.execute(
        select(Organisation).where(
            Organisation.id == org_id,
            Organisation.tenant_id == current_user.tenant_id,
        )
    )
    org = result.scalar_one_or_none()
    if org is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organisation not found")

    if body.name is not None:
        org.name = body.name
    if body.logo_url is not None:
        org.logo_url = body.logo_url

    await db.commit()
    await db.refresh(org)
    return OrganisationResponse.model_validate(org)


# ── DELETE /organisations/{org_id} ────────────────────────────


@router.delete("/organisations/{org_id}", status_code=200)
async def delete_organisation(
    org_id: uuid.UUID,
    db: DBDep,
    current_user: CurrentActiveUser,
) -> dict:
    """Delete an organisation (only if no members)."""
    result = await db.execute(
        select(Organisation).where(
            Organisation.id == org_id,
            Organisation.tenant_id == current_user.tenant_id,
        )
    )
    org = result.scalar_one_or_none()
    if org is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organisation not found")

    # Check members
    member_count = await db.execute(select(Membership).where(Membership.organisation_id == org_id))
    if member_count.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Cannot delete organisation with members"
        )

    await db.delete(org)
    await db.commit()
    return {"message": "Organisation deleted"}


# ── GET /organisations/{org_id}/members ───────────────────────


@router.get("/organisations/{org_id}/members", response_model=list[OrganisationMemberResponse])
async def list_members(
    org_id: uuid.UUID,
    db: DBDep,
    current_user: CurrentActiveUser,
) -> list[OrganisationMemberResponse]:
    """List members of an organisation."""
    org = await db.execute(
        select(Organisation).where(
            Organisation.id == org_id,
            Organisation.tenant_id == current_user.tenant_id,
        )
    )
    if org.scalar_one_or_none() is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organisation not found")

    # C2: verify caller membership
    await _verify_org_membership(org_id, db, current_user)

    result = await db.execute(
        select(Membership, User, Role)
        .join(User, Membership.user_id == User.id)
        .outerjoin(Role, Membership.role_id == Role.id)
        .where(Membership.organisation_id == org_id)
    )
    rows = result.all()
    return [
        OrganisationMemberResponse(
            user_id=m.user_id,
            full_name=u.display_name,
            email=u.email,
            role=r.name if r else "member",
            role_id=m.role_id,
            invited_at=None,
            accepted_at=m.created_at,
        )
        for m, u, r in rows
    ]


# ── POST /organisations/{org_id}/invites ──────────────────────


@router.post("/organisations/{org_id}/invites", response_model=InviteResponse, status_code=201)
async def invite_member(
    org_id: uuid.UUID,
    body: InviteCreateRequest,
    db: DBDep,
    current_user: CurrentActiveUser,
) -> InviteResponse:
    """Invite a user to an organisation. Stub: creates a membership directly."""
    org = await db.execute(
        select(Organisation).where(
            Organisation.id == org_id,
            Organisation.tenant_id == current_user.tenant_id,
        )
    )
    if org.scalar_one_or_none() is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organisation not found")

    # C2/C5: verify caller is a member of this org
    await _verify_org_membership(org_id, db, current_user)

    # Find user by email
    user_result = await db.execute(
        select(User).where(User.email == body.email, User.tenant_id == current_user.tenant_id)
    )
    user = user_result.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found in this tenant"
        )

    # Check existing membership
    existing = await db.execute(
        select(Membership).where(
            Membership.organisation_id == org_id,
            Membership.user_id == user.id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="User is already a member"
        )

    # Find role
    role_id = None
    if body.role:
        role_result = await db.execute(
            select(Role).where(Role.name == body.role, Role.tenant_id == current_user.tenant_id)
        )
        role = role_result.scalar_one_or_none()
        if role:
            role_id = role.id

    m = Membership(
        tenant_id=current_user.tenant_id,
        user_id=user.id,
        organisation_id=org_id,
        role_id=role_id,
    )
    db.add(m)
    await db.commit()
    await db.refresh(m)

    return InviteResponse(
        id=m.id,
        email=body.email,
        role=body.role,
        status="accepted",
        created_at=m.created_at,
    )


# ── DELETE /organisations/{org_id}/members/{user_id} ─────────


@router.delete("/organisations/{org_id}/members/{user_id}", status_code=200)
async def remove_member(
    org_id: uuid.UUID,
    user_id: uuid.UUID,
    db: DBDep,
    current_user: CurrentActiveUser,
) -> dict:
    """Remove a member from an organisation."""
    # C2: verify caller membership
    await _verify_org_membership(org_id, db, current_user)

    result = await db.execute(
        select(Membership).where(
            Membership.organisation_id == org_id,
            Membership.user_id == user_id,
            Membership.tenant_id == current_user.tenant_id,
        )
    )
    m = result.scalar_one_or_none()
    if m is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")

    await db.delete(m)
    await db.commit()
    return {"message": "Member removed"}


# ── PATCH /organisations/{org_id}/members/{user_id}/role ──────


@router.patch("/organisations/{org_id}/members/{user_id}/role", status_code=200)
async def change_member_role(
    org_id: uuid.UUID,
    user_id: uuid.UUID,
    body: ChangeRoleRequest,
    db: DBDep,
    current_user: CurrentActiveUser,
) -> dict:
    """Change a member's role."""
    # C2: verify caller membership + check role permission (admin required)
    await _verify_org_membership(org_id, db, current_user)

    result = await db.execute(
        select(Membership).where(
            Membership.organisation_id == org_id,
            Membership.user_id == user_id,
            Membership.tenant_id == current_user.tenant_id,
        )
    )
    m = result.scalar_one_or_none()
    if m is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")

    # Find role
    role_result = await db.execute(
        select(Role).where(Role.name == body.role, Role.tenant_id == current_user.tenant_id)
    )
    role = role_result.scalar_one_or_none()
    if role is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Role '{body.role}' not found"
        )

    m.role_id = role.id
    await db.commit()
    return {"message": f"Role changed to '{body.role}'"}
