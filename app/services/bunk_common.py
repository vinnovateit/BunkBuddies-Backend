from __future__ import annotations

import random
import re
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
    "R",
    "T",
}
LH_BLOCKS = {
    "A",
    "B",
    "C",
    "D",
    "E",
    "F",
    "H",
    "J",
    "S",
}
MH_ROOM_SIZES = [2, 3, 4, 6]
LH_ROOM_SIZES = [2, 3, 4, 5, 6]
REG_NO_PATTERN = re.compile(r"^(\d{2})[A-Z]{3}\d{4}$", flags=re.IGNORECASE)


def size_to_capacity(size: GroupSize | str) -> int:
    raw = size.value if isinstance(size, GroupSize) else str(size or "").strip()
    match = re.fullmatch(r"(\d+)(?:\s*-\s*bedded)?", raw, flags=re.IGNORECASE)
    if not match:
        raise ValueError(f"Invalid group size value: {size!r}")

    value = int(match.group(1))
    if value not in {1, 2, 3, 4, 5, 6, 8}:
        raise ValueError(f"Unsupported group size value: {size!r}")

    return value


def verify_blocks(hostel_type: HostelType, group_data: dict) -> bool:
    valid_blocks = MH_BLOCKS if hostel_type == HostelType.MH else LH_BLOCKS
    for key in ("block1", "block2", "block3"):
        value = group_data.get(key)
        if value and value not in valid_blocks:
            return False
    return True


def reg_no_joining_year(reg_no: str | None) -> int | None:
    cleaned = str(reg_no or "").strip().upper()
    match = REG_NO_PATTERN.fullmatch(cleaned)
    if not match:
        return None
    return 2000 + int(match.group(1))


def is_reg_no_senior_to(candidate_reg_no: str | None, other_reg_no: str | None) -> bool | None:
    candidate_year = reg_no_joining_year(candidate_reg_no)
    other_year = reg_no_joining_year(other_reg_no)
    if candidate_year is None or other_year is None:
        return None
    return candidate_year < other_year


def is_reg_no_junior_to(candidate_reg_no: str | None, other_reg_no: str | None) -> bool | None:
    candidate_year = reg_no_joining_year(candidate_reg_no)
    other_year = reg_no_joining_year(other_reg_no)
    if candidate_year is None or other_year is None:
        return None
    return candidate_year > other_year


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
