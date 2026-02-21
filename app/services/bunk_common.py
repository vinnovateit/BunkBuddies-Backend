from __future__ import annotations

import random
import string
from datetime import datetime, timezone

from bson import ObjectId

from app.schemas import GroupSize, HostelType


MH_BLOCKS = {
    "A",
    "B",
    "B Annex",
    "C",
    "D",
    "D Annex",
    "E",
    "F",
    "G",
    "H",
    "J",
    "K",
    "L",
    "M",
    "N",
    "P",
    "Q",
    "R",
    "S",
    "T",
}
LH_BLOCKS = {"A", "B", "C", "D", "E", "E Annex", "F", "G", "H", "J"}


def size_to_capacity(size: GroupSize) -> int:
    mapping = {
        GroupSize.ONE: 1,
        GroupSize.TWO: 2,
        GroupSize.THREE: 3,
        GroupSize.FOUR: 4,
        GroupSize.SIX: 6,
        GroupSize.EIGHT: 8,
    }
    return mapping[size]


def verify_blocks(hostel_type: HostelType, group_data: dict) -> bool:
    valid_blocks = MH_BLOCKS if hostel_type == HostelType.MH else LH_BLOCKS
    for key in ("block1", "block2", "block3"):
        value = group_data.get(key)
        if value and value not in valid_blocks:
            return False
    return True


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def object_id_from_str(value: str) -> ObjectId | None:
    try:
        return ObjectId(value)
    except Exception:
        return None


async def generate_group_code(groups_collection) -> str:
    while True:
        code = "".join(random.choices(string.ascii_lowercase + string.digits, k=6))
        existing = await groups_collection.find_one({"groupCode": code})
        if not existing:
            return code


def serialize_for_api(value):
    if isinstance(value, ObjectId):
        return str(value)

    if isinstance(value, list):
        return [serialize_for_api(item) for item in value]

    if isinstance(value, dict):
        serialized = {}
        for key, item in value.items():
            if key == "_id":
                if "id" not in value:
                    serialized["id"] = str(item)
                continue
            serialized[key] = serialize_for_api(item)
        return serialized

    return value
