"""Response schemas"""
from datetime import datetime
from pydantic import BaseModel
from typing import Optional


class ResponseDraftSchema(BaseModel):
    """Response draft schema"""
    id: Optional[int] = None
    review_id: int
    text: str
    variant_number: int
    is_selected: bool = False
    
    class Config:
        from_attributes = True


class ResponseSchema(BaseModel):
    """Response schema"""
    id: Optional[int] = None
    review_id: int
    draft_id: Optional[int] = None
    text: str
    status: str = "draft"
    created_at: Optional[datetime] = None
    sent_at: Optional[datetime] = None
    error_message: Optional[str] = None
    
    class Config:
        from_attributes = True


class ResponseCreateSchema(BaseModel):
    """Create response request"""
    review_id: int
    text: str
    draft_id: Optional[int] = None
