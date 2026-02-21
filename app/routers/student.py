import re

from fastapi import APIRouter, Depends, HTTPException

from app.auth.dependencies import get_current_auth_user
from app.database import get_database
from app.schemas import CurrentAuthUser, UpdateStudentRequest
from app.services import GroupService, StudentService, UserService

router = APIRouter(prefix="/student", tags=["student"])


def _extract_reg_no_from_email(email: str) -> str | None:
    local_part = email.split("@")[0].upper().replace(".", "")
    if re.match(r"^\d{2}[A-Z]{3}\d{4}$", local_part):
        return local_part
    return None


def _fallback_reg_no(email: str, uid: str) -> str:
    local_part = email.split("@")[0].upper()
    normalized = re.sub(r"[^A-Z0-9]", "", local_part)
    if normalized:
        return normalized
    return f"UID{uid}"


async def _ensure_student_profile(
    student_service: StudentService,
    user_service: UserService,
    current_user: CurrentAuthUser,
) -> dict | None:
    student = await student_service.get_by_uid(current_user.uid)
    if student:
        return student

    user = await user_service.get_user_by_id(current_user.user_id)
    if not user:
        return None

    reg_no = _extract_reg_no_from_email(user.email) or _fallback_reg_no(user.email, current_user.uid)
    name = f"{user.first_name} {user.last_name}".strip() or user.email.split("@")[0]
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

    return {"message": "User found", "user": user_with_admin_details}


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

    return {"message": "User updated", "user": updated_student}
