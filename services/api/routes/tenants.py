from typing import List
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from packages.core.database import get_db
from packages.core.models import Tenant, Membership, User, RoleEnum, AuditEvent
from services.api.dependencies import get_current_user, get_tenant_context, require_role, TenantContext
from services.api.exceptions import ConflictException, NotFoundException
from services.api.schemas.tenant import (
    CreateTenantRequest,
    TenantResponse,
    MemberResponse,
    AddMemberRequest,
)

router = APIRouter(prefix="/tenants", tags=["Tenants & Workspaces"])

@router.post("", response_model=TenantResponse, status_code=status.HTTP_201_CREATED)
async def create_tenant(
    req: CreateTenantRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new workspace and assign caller as OWNER in a single transaction."""
    # Check slug uniqueness
    existing = await db.execute(select(Tenant).where(Tenant.slug == req.slug))
    if existing.scalar_one_or_none():
        raise ConflictException(f"Workspace slug '{req.slug}' is already taken.", code="SLUG_ALREADY_EXISTS")

    tenant = Tenant(name=req.name, slug=req.slug)
    db.add(tenant)
    await db.flush()

    # Create Owner membership
    membership = Membership(
        tenant_id=tenant.id,
        user_id=current_user.id,
        role=RoleEnum.OWNER,
    )
    db.add(membership)

    # Log audit event
    audit = AuditEvent(
        tenant_id=tenant.id,
        actor_user_id=current_user.id,
        action="tenant.create",
        resource_type="tenant",
        resource_id=tenant.id,
        event_metadata={"name": tenant.name, "slug": tenant.slug},
    )
    db.add(audit)

    await db.commit()
    await db.refresh(tenant)

    return TenantResponse(
        id=tenant.id,
        name=tenant.name,
        slug=tenant.slug,
        created_at=tenant.created_at,
        role=RoleEnum.OWNER,
    )

@router.get("", response_model=List[TenantResponse])
async def list_tenants(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all workspaces the authenticated user belongs to."""
    query = (
        select(Tenant, Membership.role)
        .join(Membership, Tenant.id == Membership.tenant_id)
        .where(Membership.user_id == current_user.id)
    )
    result = await db.execute(query)
    rows = result.all()

    return [
        TenantResponse(
            id=tenant.id,
            name=tenant.name,
            slug=tenant.slug,
            created_at=tenant.created_at,
            role=role,
        )
        for tenant, role in rows
    ]

@router.get("/{tenant_id}/members", response_model=List[MemberResponse])
async def list_members(
    ctx: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db),
):
    """List members of a workspace (Requires tenant membership)."""
    query = (
        select(Membership, User)
        .join(User, Membership.user_id == User.id)
        .where(Membership.tenant_id == ctx.tenant_id)
    )
    result = await db.execute(query)
    rows = result.all()

    return [
        MemberResponse(
            id=membership.id,
            user_id=user.id,
            email=user.email,
            role=membership.role,
            created_at=membership.created_at,
        )
        for membership, user in rows
    ]

@router.post(
    "/{tenant_id}/members",
    response_model=MemberResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_role([RoleEnum.OWNER, RoleEnum.ADMIN]))],
)
async def add_member(
    req: AddMemberRequest,
    ctx: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db),
):
    """Add a member to a workspace (Owner/Admin only)."""
    user_res = await db.execute(select(User).where(User.email == req.email))
    target_user = user_res.scalar_one_or_none()

    if not target_user:
        # Create user account stub for invitation
        target_user = User(email=req.email, auth_subject=req.email)
        db.add(target_user)
        await db.flush()

    # Check if already a member
    mem_res = await db.execute(
        select(Membership).where(
            Membership.tenant_id == ctx.tenant_id,
            Membership.user_id == target_user.id,
        )
    )
    if mem_res.scalar_one_or_none():
        raise ConflictException("User is already a member of this workspace.", code="ALREADY_MEMBER")

    membership = Membership(
        tenant_id=ctx.tenant_id,
        user_id=target_user.id,
        role=req.role,
    )
    db.add(membership)

    audit = AuditEvent(
        tenant_id=ctx.tenant_id,
        actor_user_id=ctx.user.id,
        action="member.add",
        resource_type="membership",
        resource_id=target_user.id,
        event_metadata={"email": req.email, "role": req.role.value},
    )
    db.add(audit)

    await db.commit()
    await db.refresh(membership)

    return MemberResponse(
        id=membership.id,
        user_id=target_user.id,
        email=target_user.email,
        role=membership.role,
        created_at=membership.created_at,
    )
