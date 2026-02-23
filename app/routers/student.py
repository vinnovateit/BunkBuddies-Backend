import re

from fastapi import APIRouter, Depends, HTTPException

from app.auth.dependencies import get_current_auth_user
from app.database import get_database
from app.schemas import CurrentAuthUser, UpdateStudentRequest
from app.services import GroupService, StudentService, UserService
from app.services.bunk_common import serialize_for_api

router = APIRouter(prefix="/student", tags=["student"])


_REG_NO_CANDIDATE_PATTERN = re.compile(r"\b([0-9Oo]{2}[A-Za-z]{3}[0-9Oo]{4})\b")
_REG_NO_NUMERIC_INDEXES = (0, 1, 5, 6, 7, 8)
_REG_NO_ALPHA_INDEXES = (2, 3, 4)


def _normalize_reg_no_candidate(raw: str) -> str | None:
    cleaned = re.sub(r"[^A-Za-z0-9]", "", raw or "").upper()
    if len(cleaned) != 9:
        return None

    chars = list(cleaned)
    for index in _REG_NO_NUMERIC_INDEXES:
        if chars[index] == "O":
            chars[index] = "0"
        if not chars[index].isdigit():
            return None

    for index in _REG_NO_ALPHA_INDEXES:
        if not chars[index].isalpha():
            return None

    return "".join(chars)


def _extract_reg_no_from_text(value: str | None) -> str | None:
    if not value:
        return None

    match = _REG_NO_CANDIDATE_PATTERN.search(value)
    if not match:
        return None

    return _normalize_reg_no_candidate(match.group(1))


def _extract_reg_no_from_email(email: str) -> str | None:
    local_part = email.split("@")[0]
    return _extract_reg_no_from_text(local_part)


def _fallback_reg_no(uid: str) -> str:
    return f"UID{uid}"


def _is_valid_reg_no(value: str | None) -> bool:
    if not value:
        return False
    normalized = _normalize_reg_no_candidate(value)
    return normalized == value.upper()


def _strip_reg_no_from_name(value: str, reg_no: str | None) -> str:
    cleaned = re.sub(r"\s+", " ", (value or "").strip())
    if not cleaned:
        return ""

    if reg_no:
        cleaned = re.sub(re.escape(reg_no), "", cleaned, flags=re.IGNORECASE).strip()

    cleaned = _REG_NO_CANDIDATE_PATTERN.sub("", cleaned).strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned


async def _ensure_student_profile(
    student_service: StudentService,
    user_service: UserService,
    current_user: CurrentAuthUser,
) -> dict | None:
    student = await student_service.get_by_uid(current_user.uid)
    if student:
        updates = {}
        current_name = (student.get("name") or "").strip()
        current_reg = (student.get("regNo") or "").strip()

        inferred_reg_from_name = _extract_reg_no_from_text(current_name)
        inferred_reg_from_email = _extract_reg_no_from_email(student.get("email") or "")
        resolved_reg = inferred_reg_from_name or inferred_reg_from_email

        if resolved_reg and resolved_reg != current_reg:
            updates["regNo"] = resolved_reg
            current_reg = resolved_reg

        if not _is_valid_reg_no(current_reg) and inferred_reg_from_name:
            updates["regNo"] = inferred_reg_from_name
            current_reg = inferred_reg_from_name

        cleaned_name = _strip_reg_no_from_name(current_name, current_reg)
        if cleaned_name and cleaned_name != current_name:
            updates["name"] = cleaned_name

        if updates:
            await student_service.update_by_uid(current_user.uid, updates)
            return await student_service.get_by_uid(current_user.uid)
        return student

    user = await user_service.get_user_by_id(current_user.user_id)
    if not user:
        return None

    full_name = f"{user.first_name} {user.last_name}".strip()
    reg_no = _extract_reg_no_from_email(user.email) or _extract_reg_no_from_text(full_name) or _fallback_reg_no(current_user.uid)
    name = _strip_reg_no_from_name(full_name, reg_no) or user.email.split("@")[0].replace(".", " ").strip()
    student_payload = {
        "regNo": reg_no,
        "name": name,
        "email": user.email,
        "firebaseUID": current_user.uid,
        "photoURL": user.picture,
    }

    duplicate_reg = await student_service.get_by_reg_no(reg_no)
    if duplicate_reg:
        await student_service.collection.update_one(
            {"_id": duplicate_reg["_id"]},
            {"$set": student_payload},
        )
    else:
        await student_service.create_student(student_payload)

    return await student_service.get_by_uid(current_user.uid)


@router.get("/getStudent")
async def get_student(current_user: CurrentAuthUser = Depends(get_current_auth_user)):
    db = get_database()
    student_service = StudentService(db)
    group_service = GroupService(db)
    user_service = UserService(db)

    student = await _ensure_student_profile(student_service, user_service, current_user)
    if not student:
        raise HTTPException(status_code=404, detail="User not found")

    admin_details = None
    group = None

    if student.get("groupId"):
        group = await group_service.get_by_id(student["groupId"])
        if group:
            members = await student_service.list_by_uids(group.get("studentUids", []))
            group["students"] = members
            admin = next((item for item in members if item.get("firebaseUID") == group.get("adminUID")), None)
            if admin:
                admin_details = {
                    "CGPA": admin.get("CGPA"),
                }
            student["group"] = group

    user_with_admin_details = {
        **student,
        "adminCGPA": admin_details.get("CGPA") if admin_details else None,
    }

    return {"message": "User found", "user": serialize_for_api(user_with_admin_details)}


@router.get("/getStudentLite")
async def get_student_lite(current_user: CurrentAuthUser = Depends(get_current_auth_user)):
    db = get_database()
    student_service = StudentService(db)
    group_service = GroupService(db)
    user_service = UserService(db)

    student = await _ensure_student_profile(student_service, user_service, current_user)
    if not student:
        raise HTTPException(status_code=404, detail="User not found")

    group_summary = None
    if student.get("groupId"):
        group = await group_service.get_by_id(student["groupId"])
        if group:
            group_summary = {
                "id": group.get("id"),
                "adminUID": group.get("adminUID"),
            }
        else:
            group_summary = {"id": student.get("groupId")}

    user_lite = {
        "firebaseUID": student.get("firebaseUID"),
        "regNo": student.get("regNo"),
        "hostelType": student.get("hostelType"),
        "group": group_summary,
        "hasGroup": bool(group_summary),
    }
    return {"message": "User found", "user": serialize_for_api(user_lite)}


@router.put("/updateStudent")
async def update_student(
    payload: UpdateStudentRequest,
    current_user: CurrentAuthUser = Depends(get_current_auth_user),
):
    db = get_database()
    student_service = StudentService(db)
    user_service = UserService(db)

    student = await _ensure_student_profile(student_service, user_service, current_user)
    if not student:
        raise HTTPException(status_code=404, detail="User not found")

    update_data = payload.model_dump(exclude_none=True)
    updated_student = await student_service.update_by_uid(current_user.uid, update_data)

    return {"message": "User updated", "user": serialize_for_api(updated_student)}
