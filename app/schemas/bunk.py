from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class HostelType(str, Enum):
    MH = "MH"
    LH = "LH"


class GroupType(str, Enum):
    AC = "AC"
    NON_AC = "NON-AC"


class GroupSize(str, Enum):
    ONE = "1-Bedded"
    TWO = "2-Bedded"
    THREE = "3-Bedded"
    FOUR = "4-Bedded"
    SIX = "6-Bedded"
    EIGHT = "8-Bedded"


class GroupRequestStatus(str, Enum):
    PENDING = "PENDING"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"


class SignupStudentRequest(BaseModel):
    regNo: str = Field(pattern=r"^\d{2}[A-Z]{3}\d{4}$")
    name: str
    email: EmailStr = Field(pattern=r".*@vitstudent\.ac\.in$")
    phone: Optional[str] = None


class UpdateStudentRequest(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    CGPA: Optional[float] = Field(default=None, ge=0, le=10)
    description: Optional[str] = None
    hostelType: Optional[HostelType] = None


class CreateGroupRequest(BaseModel):
    groupName: str
    type: GroupType
    groupSize: GroupSize
    block1: str
    block2: str
    block3: str
    preferences: Optional[str] = None


class UpdateGroupRequest(BaseModel):
    groupCode: Optional[str] = Field(default=None, max_length=10)
    groupName: Optional[str] = None
    hostelType: Optional[HostelType] = None
    type: Optional[GroupType] = None
    groupSize: Optional[GroupSize] = None
    block1: Optional[str] = None
    block2: Optional[str] = None
    block3: Optional[str] = None
    preferences: Optional[str] = None


class GroupQueryRequest(BaseModel):
    offset: int = 0
    limit: int = 20
    type: Optional[GroupType] = None
    groupSize: Optional[GroupSize] = None
    block1: Optional[str] = None
    block2: Optional[str] = None
    block3: Optional[str] = None
    vacancy: Optional[int] = None
    minCGPA: Optional[float] = None
    maxCGPA: Optional[float] = None

    @field_validator("offset", "limit")
    @classmethod
    def non_negative(cls, value: int) -> int:
        return max(value, 0)


class CurrentAuthUser(BaseModel):
    model_config = ConfigDict(extra="ignore")

    user_id: str
    uid: str
    email: str
