"""Review model"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean
from app.database import Base


class Review(Base):
    """Review from Ozon marketplace"""
    
    __tablename__ = "reviews"
    
    id = Column(Integer, primary_key=True, index=True)
    ozon_review_id = Column(String, unique=True, index=True)  # Unique ID from Ozon
    product_id = Column(String, index=True)
    product_name = Column(String)
    customer_name = Column(String)
    rating = Column(Integer)  # 1-5
    text = Column(Text)
    sentiment = Column(String, nullable=True)  # positive, neutral, negative
    category = Column(String, nullable=True)  # quality, delivery, packaging, etc.
    answered = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    fetched_at = Column(DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f"<Review {self.ozon_review_id}: '{self.text[:50]}...'>"
