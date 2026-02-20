from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.schemas import GroupRequestStatus, GroupSize, GroupType, HostelType


class Student(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: Optional[str] = Field(default=None, alias="_id")
    regNo: str
    name: str
    email: str
    phone: Optional[str] = None
    photoURL: Optional[str] = None
    firebaseUID: str
    hostelType: Optional[HostelType] = None
    CGPA: Optional[float] = None
    description: Optional[str] = None
    groupId: Optional[str] = None


class Group(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: Optional[str] = Field(default=None, alias="_id")
    groupName: str
    hostelType: HostelType
    type: GroupType
    groupSize: GroupSize
    block1: str
    block2: str
    block3: str
    preferences: Optional[str] = None
    groupCode: Optional[str] = None
    adminUID: str
    createdAt: datetime = Field(default_factory=datetime.utcnow)
    studentUids: list[str] = Field(default_factory=list)


class GroupRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: Optional[str] = Field(default=None, alias="_id")
    status: GroupRequestStatus = GroupRequestStatus.PENDING
    groupId: str
    studentRegNo: str
