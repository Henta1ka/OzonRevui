"""Review schemas"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class ReviewSchema(BaseModel):
    """Review schema for response"""
    id: int
    ozon_review_id: str
    product_name: Optional[str] = None
    customer_name: Optional[str] = None
    rating: Optional[int] = None
    text: str
    sentiment: Optional[str] = None
    category: Optional[str] = None
    answered: bool = False
    created_at: datetime
    
    class Config:
        from_attributes = True


class ReviewDetail(ReviewSchema):
    """Detailed review schema with drafts"""
    pass
