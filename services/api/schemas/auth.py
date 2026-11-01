from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, EmailStr, Field
from packages.core.models.tenant import RoleEnum

class UserRegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, description="Password must be at least 8 characters")
    name: Optional[str] = None

class UserLoginRequest(BaseModel):
    email: EmailStr
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    email: str

class TenantSummary(BaseModel):
    id: str
    name: str
    role: RoleEnum

class CurrentUserResponse(BaseModel):
    id: str
    email: str
    tenants: List[TenantSummary]
