from __future__ import annotations
from typing import Optional, List
import re
from pydantic import BaseModel, Field, field_validator

from enum import Enum
import re
from typing import List, Optional

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
    FIVE = "5-Bedded"
    SIX = "6-Bedded"
    EIGHT = "8-Bedded"


class GroupRequestStatus(str, Enum):
    PENDING = "PENDING"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"


class GroupSortBy(str, Enum):
    VACANCY = "vacancy"
    CGPA = "cgpa"


class SortOrder(str, Enum):
    ASC = "asc"
    DESC = "desc"


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
    rank: Optional[int] = None
    sleepTime: Optional[float] = None
    wakeTime: Optional[float] = None
    cleanliness: Optional[int] = Field(default=None, ge=0, le=5)
    socialScene: Optional[int] = Field(default=None, ge=0, le=5)
    languages: Optional[List[str]] = None
    interests: Optional[str] = None
    quizCompleted: Optional[bool] = None

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value

        trimmed = value.strip()
        if not trimmed:
            return None

        digits = re.sub(r"\D", "", trimmed)
        if digits.startswith("91") and len(digits) == 12:
            digits = digits[2:]

        if not re.fullmatch(r"[6-9]\d{9}", digits):
            raise ValueError("Contact number must be a valid 10-digit Indian mobile number")

        return f"+91{digits}"


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
    page: int = 1
    pageSize: int = 20
    search: Optional[str] = None
    type: Optional[GroupType] = None
    groupSize: Optional[GroupSize] = None
    groupSizes: list[GroupSize] = Field(default_factory=list)
    block1: Optional[str] = None
    block2: Optional[str] = None
    block3: Optional[str] = None
    blocks: list[str] = Field(default_factory=list)
    vacancy: Optional[int] = None
    minCGPA: Optional[float] = None
    maxCGPA: Optional[float] = None
    sortBy: Optional[GroupSortBy] = None
    sortOrder: SortOrder = SortOrder.DESC

    @field_validator("offset", "limit")
    @classmethod
    def non_negative(cls, value: int) -> int:
        return max(value, 0)

    @field_validator("page", "pageSize")
    @classmethod
    def min_one(cls, value: int) -> int:
        return max(value, 1)

    @field_validator("blocks")
    @classmethod
    def normalize_blocks(cls, values: list[str]) -> list[str]:
        normalized: list[str] = []
        seen: set[str] = set()
        for value in values:
            text = str(value or "").strip()
            if not text:
                continue
            key = text.upper()
            if key in seen:
                continue
            seen.add(key)
            normalized.append(text)
        return normalized


class CurrentAuthUser(BaseModel):
    model_config = ConfigDict(extra="ignore")

    user_id: str
    uid: str
    email: str
