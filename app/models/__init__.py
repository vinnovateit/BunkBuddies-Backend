"""User Database Model"""
from typing import Optional
from datetime import datetime
from pydantic import BaseModel, EmailStr, Field


class User(BaseModel):
    """User model for MongoDB"""
    id: Optional[str] = Field(None, alias="_id")
    email: str
    first_name: str
    last_name: str
    picture: Optional[str] = None
    google_id: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        populate_by_name = True
        json_schema_extra = {
            "example": {
                "email": "user@example.com",
                "first_name": "John",
                "last_name": "Doe",
                "picture": "https://example.com/picture.jpg",
                "google_id": "google_id_123"
            }
        }


from app.models.bunk import Group, GroupRequest, Student
