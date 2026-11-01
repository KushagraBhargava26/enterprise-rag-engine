import enum
from datetime import datetime
from typing import List, Optional
from sqlalchemy import String, ForeignKey, Enum, DateTime, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from packages.core.database import Base
from packages.core.models.base import TimestampMixin, generate_uuid, utc_now

class RoleEnum(str, enum.Enum):
    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"
    VIEWER = "viewer"

class Tenant(Base, TimestampMixin):
    __tablename__ = "tenants"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)

    memberships: Mapped[List["Membership"]] = relationship("Membership", back_populates="tenant", cascade="all, delete-orphan")
    documents: Mapped[List["Document"]] = relationship("Document", back_populates="tenant", cascade="all, delete-orphan")

class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    auth_subject: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    hashed_password: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    memberships: Mapped[List["Membership"]] = relationship("Membership", back_populates="user", cascade="all, delete-orphan")

class Membership(Base, TimestampMixin):
    __tablename__ = "memberships"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    role: Mapped[RoleEnum] = mapped_column(Enum(RoleEnum), default=RoleEnum.MEMBER, nullable=False)

    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="memberships")
    user: Mapped["User"] = relationship("User", back_populates="memberships")

    __table_args__ = (
        UniqueConstraint("tenant_id", "user_id", name="uq_tenant_user_membership"),
        Index("ix_membership_tenant_user", "tenant_id", "user_id"),
    )
