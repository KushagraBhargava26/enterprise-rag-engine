from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from packages.core.database import get_db
from packages.core.models import User, Tenant, Membership
from packages.core.security import hash_password, verify_password, create_access_token
from services.api.dependencies import get_current_user
from services.api.exceptions import ConflictException, UnauthorizedException
from services.api.schemas.auth import (
    UserRegisterRequest,
    UserLoginRequest,
    TokenResponse,
    CurrentUserResponse,
    TenantSummary,
)

router = APIRouter(tags=["Authentication & Me"])

@router.post("/auth/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(req: UserRegisterRequest, db: AsyncSession = Depends(get_db)):
    """Register a new user account."""
    existing = await db.execute(select(User).where(User.email == req.email))
    if existing.scalar_one_or_none():
        raise ConflictException("A user with this email already exists.", code="USER_ALREADY_EXISTS")

    hashed = hash_password(req.password)
    user = User(
        email=req.email,
        auth_subject=req.email,
        hashed_password=hashed,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    token = create_access_token({"sub": user.id, "email": user.email})
    return TokenResponse(access_token=token, user_id=user.id, email=user.email)

@router.post("/auth/login", response_model=TokenResponse)
async def login(req: UserLoginRequest, db: AsyncSession = Depends(get_db)):
    """Authenticate with email and password to receive a JWT."""
    result = await db.execute(select(User).where(User.email == req.email))
    user = result.scalar_one_or_none()

    if not user or not user.hashed_password or not verify_password(req.password, user.hashed_password):
        raise UnauthorizedException("Invalid email or password.", code="INVALID_CREDENTIALS")

    token = create_access_token({"sub": user.id, "email": user.email})
    return TokenResponse(access_token=token, user_id=user.id, email=user.email)

@router.get("/me", response_model=CurrentUserResponse)
async def get_me(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return the authenticated user and all accessible workspaces."""
    query = (
        select(Membership, Tenant)
        .join(Tenant, Membership.tenant_id == Tenant.id)
        .where(Membership.user_id == current_user.id)
    )
    result = await db.execute(query)
    rows = result.all()

    tenants = [
        TenantSummary(id=tenant.id, name=tenant.name, role=membership.role)
        for membership, tenant in rows
    ]

    return CurrentUserResponse(
        id=current_user.id,
        email=current_user.email,
        tenants=tenants,
    )
