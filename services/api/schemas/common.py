from typing import Optional, Dict, Any, Generic, TypeVar, List
from pydantic import BaseModel, Field

T = TypeVar("T")

class ErrorDetail(BaseModel):
    code: str
    message: str
    request_id: str
    details: Optional[Dict[str, Any]] = Field(default_factory=dict)

class ErrorEnvelope(BaseModel):
    error: ErrorDetail

class PaginatedResponse(BaseModel, Generic[T]):
    items: List[T]
    limit: int
    cursor: Optional[str] = None
    has_more: bool = False
