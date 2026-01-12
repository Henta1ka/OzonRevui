"""Settings schemas"""
from pydantic import BaseModel


class SettingsSchema(BaseModel):
    """Settings schema"""
    key: str
    value: str
    
    class Config:
        from_attributes = True
