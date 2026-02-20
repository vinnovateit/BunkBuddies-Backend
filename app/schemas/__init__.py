"""User Request/Response Schemas"""
from typing import Optional
from pydantic import BaseModel, EmailStr


class UserResponse(BaseModel):
    """User response schema"""
    id: str
    email: str
    first_name: str
    last_name: str
    picture: Optional[str] = None
    
    class Config:
        from_attributes = True


class UserLogin(BaseModel):
    """User login request schema"""
    email: str
    first_name: str
    last_name: str
    picture: Optional[str] = None
    google_id: str


class TokenResponse(BaseModel):
    """Token response schema"""
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


from app.schemas.bunk import (
    CreateGroupRequest,
    CurrentAuthUser,
    GroupQueryRequest,
    GroupRequestStatus,
    GroupSize,
    GroupType,
    HostelType,
    SignupStudentRequest,
    UpdateGroupRequest,
    UpdateStudentRequest,
)
