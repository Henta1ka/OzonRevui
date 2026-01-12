"""Settings model for response configuration"""
from sqlalchemy import Column, Integer, String, Text
from app.database import Base


class Settings(Base):
    """Global settings for response generation and sending"""
    
    __tablename__ = "settings"
    
    id = Column(Integer, primary_key=True, index=True)
    key = Column(String, unique=True, index=True)
    value = Column(Text)
    
    def __repr__(self):
        return f"<Settings {self.key}={self.value}>"
