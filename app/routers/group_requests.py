from fastapi import APIRouter, Depends, HTTPException

from app.auth.dependencies import get_current_auth_user
from app.database import get_database
from app.schemas import CurrentAuthUser, GroupRequestStatus
from app.services import GroupRequestService, GroupService, StudentService
from app.services.bunk_common import serialize_for_api

router = APIRouter(prefix="/groupRequest", tags=["groupRequest"])


@router.get("/listRequests")
async def list_group_requests(current_user: CurrentAuthUser = Depends(get_current_auth_user)):
    db = get_database()
    student_service = StudentService(db)
    group_service = GroupService(db)

    admin = await student_service.get_by_uid(current_user.uid)
    if not admin:
        raise HTTPException(status_code=400, detail="Student doesn't exist")

    if not admin.get("groupId"):
        raise HTTPException(status_code=400, detail="You are not in any group")

    group = await group_service.get_by_id(admin["groupId"])
    if not group or group["adminUID"] != current_user.uid:
        raise HTTPException(status_code=400, detail="You are not an admin")

    requests = await group_service.get_pending_requests_for_admin(current_user.uid)
    return {"message": "Requests fetched successfully", "requests": serialize_for_api(requests)}


@router.post("/joinRequest/{id}")
async def request_join_group(
    id: str,
    current_user: CurrentAuthUser = Depends(get_current_auth_user),
):
    db = get_database()
    group_service = GroupService(db)
    student_service = StudentService(db)
    request_service = GroupRequestService(db)

    group = await group_service.get_by_id(id)
    if not group:
        raise HTTPException(status_code=400, detail="Group doesn't exist")

    student = await student_service.get_by_uid(current_user.uid)
    if not student:
        raise HTTPException(status_code=400, detail="Student doesn't exist")
    if not student.get("hostelType"):
        raise HTTPException(status_code=400, detail="Student has not selected a hostel type.")

    existing_group = await group_service.get_any_group_for_student_uid(current_user.uid)
    if existing_group:
        if not student.get("groupId"):
            await student_service.set_group(current_user.uid, existing_group["id"])
        if student.get("regNo"):
            await request_service.delete_all_for_student(student["regNo"])
        raise HTTPException(status_code=400, detail="You are already in a group")

    if not group_service.is_hostel_compatible(student, group):
        raise HTTPException(
            status_code=403,
            detail="You can only request to join rooms from your own hostel type.",
        )

    existing = await request_service.get_existing(id, student["regNo"])
    if existing:
        raise HTTPException(status_code=400, detail="You have already sent a request")

    if student.get("firebaseUID") in group_service.get_student_uids(group):
        raise HTTPException(status_code=400, detail="You are already in this group")

    try:
        if await group_service.is_full(group):
            raise HTTPException(status_code=400, detail="Group is full")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    request = await request_service.create_request(id, student["regNo"])
    return {"message": "Request sent successfully", "request": serialize_for_api(request)}


@router.post("/updateRequest/{id}/{action}")
async def update_request(
    id: str,
    action: GroupRequestStatus,
    current_user: CurrentAuthUser = Depends(get_current_auth_user),
):
    db = get_database()
    group_service = GroupService(db)
    student_service = StudentService(db)
    request_service = GroupRequestService(db)

    if action == GroupRequestStatus.PENDING:
        raise HTTPException(status_code=400, detail="Invalid action")

    request = await request_service.get_by_id(id)
    if not request:
        raise HTTPException(status_code=400, detail="Request doesn't exist")

    group_id = str(request["groupId"])
    group = await group_service.get_by_id(group_id)
    if not group:
        raise HTTPException(status_code=400, detail="Group doesn't exist")

    if group["adminUID"] != current_user.uid:
        raise HTTPException(status_code=400, detail="You are not the admin")

    student = await student_service.get_by_reg_no(request["studentRegNo"])
    if not student:
        raise HTTPException(status_code=400, detail="Student doesn't exist")

    if action == GroupRequestStatus.ACCEPTED:
        if not group_service.is_hostel_compatible(student, group):
            raise HTTPException(status_code=400, detail="Student hostel type does not match this room.")

        existing_group = await group_service.get_any_group_for_student_uid(student.get("firebaseUID"))
        if existing_group:
            if not student.get("groupId"):
                await student_service.set_group(student["firebaseUID"], existing_group["id"])
            await request_service.delete_all_for_student(student["regNo"])
            raise HTTPException(
                status_code=400,
                detail="Student is already in a group. Pending requests were cleared.",
            )

        try:
            if await group_service.is_full(group):
                raise HTTPException(status_code=400, detail="Group is full")
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

        try:
            updated_group = await group_service.add_student(group, student["firebaseUID"])
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        await student_service.set_group(student["firebaseUID"], updated_group["id"])
        await request_service.delete_all_for_student(student["regNo"])
        return {
            "message": "Request updated successfully",
            "request": {
                "id": id,
                "status": GroupRequestStatus.ACCEPTED.value,
                "groupId": updated_group["id"],
                "studentRegNo": student["regNo"],
            },
        }

    updated_request = await request_service.update_status(id, action)
    return {"message": "Request updated successfully", "request": serialize_for_api(updated_request)}
