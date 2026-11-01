from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, EmailStr
from packages.core.models.tenant import RoleEnum

class CreateTenantRequest(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    slug: str = Field(min_length=2, max_length=100, pattern=r"^[a-z0-9-]+$")

class TenantResponse(BaseModel):
    id: str
    name: str
    slug: str
    created_at: datetime
    role: RoleEnum

class MemberResponse(BaseModel):
    id: str
    user_id: str
    email: str
    role: RoleEnum
    created_at: datetime

class AddMemberRequest(BaseModel):
    email: EmailStr
    role: RoleEnum = RoleEnum.MEMBER
