import uuid
from typing import Optional, List
from fastapi import Depends, Header, Path, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from packages.core.database import get_db
from packages.core.models import User, Membership, Tenant, RoleEnum
from packages.core.security import decode_access_token
from services.api.exceptions import UnauthorizedException, ForbiddenException, NotFoundException

async def get_current_user(
    authorization: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Extract and verify authenticated user from Bearer JWT token."""
    if not authorization or not authorization.startswith("Bearer "):
        raise UnauthorizedException("Missing or malformed Authorization header.")

    token = authorization.split(" ", 1)[1]
    try:
        payload = decode_access_token(token)
    except Exception:
        raise UnauthorizedException("Invalid or expired access token.")

    user_id = payload.get("sub")
    if not user_id:
        raise UnauthorizedException("Token payload missing subject.")

    query = select(User).where(User.id == user_id)
    result = await db.execute(query)
    user = result.scalar_one_or_none()

    if not user:
        raise UnauthorizedException("User not found.")

    return user

class TenantContext:
    def __init__(self, tenant: Tenant, membership: Membership, user: User):
        self.tenant = tenant
        self.membership = membership
        self.user = user

    @property
    def tenant_id(self) -> str:
        return self.tenant.id

    @property
    def role(self) -> RoleEnum:
        return self.membership.role

async def get_tenant_context(
    tenant_id: str = Path(..., description="Target Tenant UUID"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TenantContext:
    """Validate that the authenticated user is a verified member of tenant_id.
    
    Returns 404 rather than 403 on tenant mismatch to avoid leaking tenant existence.
    """
    query = (
        select(Membership, Tenant)
        .join(Tenant, Membership.tenant_id == Tenant.id)
        .where(
            Membership.tenant_id == tenant_id,
            Membership.user_id == current_user.id,
        )
    )
    result = await db.execute(query)
    row = result.first()

    if not row:
        raise NotFoundException("Workspace not found or access denied.")

    membership, tenant = row
    return TenantContext(tenant=tenant, membership=membership, user=current_user)

def require_role(allowed_roles: List[RoleEnum]):
    """Enforce required role(s) on a tenant-scoped endpoint."""
    async def role_checker(ctx: TenantContext = Depends(get_tenant_context)) -> TenantContext:
        if ctx.role not in allowed_roles:
            raise ForbiddenException(
                f"Action requires one of the following roles: {[r.value for r in allowed_roles]}."
            )
        return ctx

    return role_checker
