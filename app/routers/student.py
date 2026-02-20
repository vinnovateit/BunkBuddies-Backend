from fastapi import APIRouter, Depends, HTTPException

from app.auth.dependencies import get_current_auth_user
from app.database import get_database
from app.schemas import CurrentAuthUser, UpdateStudentRequest
from app.services import GroupService, StudentService

router = APIRouter(prefix="/s", tags=["student"])


@router.get("/")
async def get_student(current_user: CurrentAuthUser = Depends(get_current_auth_user)):
    db = get_database()
    student_service = StudentService(db)
    group_service = GroupService(db)

    student = await student_service.get_by_uid(current_user.uid)
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


@router.put("/")
async def update_student(
    payload: UpdateStudentRequest,
    current_user: CurrentAuthUser = Depends(get_current_auth_user),
):
    db = get_database()
    student_service = StudentService(db)

    student = await student_service.get_by_uid(current_user.uid)
    if not student:
        raise HTTPException(status_code=404, detail="User not found")

    update_data = payload.model_dump(exclude_none=True)
    updated_student = await student_service.update_by_uid(current_user.uid, update_data)

    return {"message": "User updated", "user": updated_student}
