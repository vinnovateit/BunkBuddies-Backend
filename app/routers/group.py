from fastapi import APIRouter, Depends, HTTPException, Query

from app.auth.dependencies import get_current_auth_user
from app.database import get_database
from app.schemas import (
    CreateGroupRequest,
    CurrentAuthUser,
    GroupQueryRequest,
    UpdateGroupRequest,
)
from app.services import GroupRequestService, GroupService, StudentService
from app.services.bunk_common import verify_blocks

router = APIRouter(prefix="/group", tags=["group"])


@router.get("/listGroups")
async def list_groups(
    offset: int = Query(0),
    limit: int = Query(20),
    type: str | None = Query(None),
    groupSize: str | None = Query(None),
    block1: str | None = Query(None),
    block2: str | None = Query(None),
    block3: str | None = Query(None),
    vacancy: int | None = Query(None),
    minCGPA: float | None = Query(None),
    maxCGPA: float | None = Query(None),
    current_user: CurrentAuthUser = Depends(get_current_auth_user),
):
    db = get_database()
    student_service = StudentService(db)
    group_service = GroupService(db)

    student = await student_service.get_by_uid(current_user.uid)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    if not student.get("hostelType"):
        raise HTTPException(status_code=400, detail="Student has not selected a hostel type.")

    query = GroupQueryRequest(
        offset=offset,
        limit=limit,
        type=type,
        groupSize=groupSize,
        block1=block1,
        block2=block2,
        block3=block3,
        vacancy=vacancy,
        minCGPA=minCGPA,
        maxCGPA=maxCGPA,
    )

    groups = await group_service.list_groups_for_student(student, query)
    return {
        "total": len(groups),
        "message": "Groups fetched successfully.",
        "groups": groups,
    }


@router.post("/createGroup")
async def create_group(
    payload: CreateGroupRequest,
    current_user: CurrentAuthUser = Depends(get_current_auth_user),
):
    db = get_database()
    student_service = StudentService(db)
    group_service = GroupService(db)

    student = await student_service.get_by_uid(current_user.uid)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    if student.get("groupId"):
        raise HTTPException(status_code=400, detail="Student already has a group.")

    if not student.get("hostelType"):
        raise HTTPException(status_code=400, detail="Student has not selected a hostel type.")

    body = payload.model_dump(exclude_none=True)
    body["hostelType"] = student["hostelType"]
    body["adminUID"] = student["firebaseUID"]

    if not verify_blocks(student["hostelType"], body):
        raise HTTPException(status_code=400, detail="Block does not exist.")

    group = await group_service.create_group(body)
    await student_service.set_group(current_user.uid, group["id"])

    return {"message": "Group created successfully.", "group": group}


@router.put("/updateGroup")
async def update_group(
    payload: UpdateGroupRequest,
    current_user: CurrentAuthUser = Depends(get_current_auth_user),
):
    db = get_database()
    student_service = StudentService(db)
    group_service = GroupService(db)

    student = await student_service.get_by_uid(current_user.uid)
    if not student or not student.get("groupId"):
        raise HTTPException(status_code=400, detail="Student doesnt have a group.")

    group = await group_service.get_by_id(student["groupId"])
    if not group:
        raise HTTPException(status_code=400, detail="Student doesnt have a group.")

    update_data = payload.model_dump(exclude_none=True)

    hostel_type = update_data.get("hostelType", group["hostelType"])
    merged = {**group, **update_data}
    if not verify_blocks(hostel_type, merged):
        raise HTTPException(status_code=400, detail="Block does not exist.")

    updated_group = await group_service.update_group(group["id"], update_data)
    return {"message": "Group updated successfully.", "group": updated_group}


@router.delete("/deleteGroup")
async def delete_group(current_user: CurrentAuthUser = Depends(get_current_auth_user)):
    db = get_database()
    student_service = StudentService(db)
    group_service = GroupService(db)
    request_service = GroupRequestService(db)

    student = await student_service.get_by_uid(current_user.uid)
    if not student or not student.get("groupId"):
        raise HTTPException(status_code=400, detail="Student doesnt have a group.")

    group = await group_service.get_by_id(student["groupId"])
    if not group:
        raise HTTPException(status_code=400, detail="Student doesnt have a group.")

    if group["adminUID"] != current_user.uid:
        raise HTTPException(status_code=400, detail="Only admins can delete group.")

    await request_service.delete_for_group(group["id"])
    await student_service.clear_group_for_uids(group.get("studentUids", []))
    await group_service.delete_group(group["id"])

    return {"message": "Group deleted successfully.", "group": {"id": group["id"]}}


@router.get("/generateCode")
async def generate_group_code(current_user: CurrentAuthUser = Depends(get_current_auth_user)):
    db = get_database()
    group_service = GroupService(db)

    group = await group_service.collection.find_one({"adminUID": current_user.uid})
    if not group:
        raise HTTPException(status_code=400, detail="You are not the admin of any group")

    if await group_service.is_full(group):
        raise HTTPException(status_code=400, detail="Group is full")

    code = await group_service.generate_code(group)
    return {"message": "Group code generated successfully", "code": code}


@router.post("/joinGroup/{code}")
async def join_group_by_code(
    code: str,
    current_user: CurrentAuthUser = Depends(get_current_auth_user),
):
    db = get_database()
    student_service = StudentService(db)
    group_service = GroupService(db)

    student = await student_service.get_by_uid(current_user.uid)
    if not student:
        raise HTTPException(status_code=400, detail="Student not found")

    if student.get("groupId"):
        raise HTTPException(status_code=400, detail="You are already in a group")

    group = await group_service.get_by_group_code(code)
    if not group:
        raise HTTPException(status_code=400, detail="Group does not exist")

    if current_user.uid == group["adminUID"] or current_user.uid in group.get("studentUids", []):
        raise HTTPException(status_code=400, detail="You have already joined this group")

    if await group_service.is_group_code_expired(group):
        raise HTTPException(status_code=400, detail="Group code has expired")

    if await group_service.is_full(group):
        raise HTTPException(status_code=400, detail="Group is full")

    updated_group = await group_service.add_student(group, current_user.uid)
    await student_service.set_group(current_user.uid, updated_group["id"])

    return {"message": "Joined group successfully", "group": updated_group}


@router.post("/leaveGroup")
async def leave_group(current_user: CurrentAuthUser = Depends(get_current_auth_user)):
    db = get_database()
    student_service = StudentService(db)
    group_service = GroupService(db)

    student = await student_service.get_by_uid(current_user.uid)
    if not student or not student.get("groupId"):
        raise HTTPException(status_code=400, detail="You are not in a group")

    group = await group_service.get_by_id(student["groupId"])
    if not group:
        raise HTTPException(status_code=400, detail="Group does not exist")

    if group["adminUID"] == current_user.uid:
        raise HTTPException(status_code=400, detail="Admins cannot leave the group")

    await group_service.remove_student(group, current_user.uid)
    await student_service.set_group(current_user.uid, None)

    return {"message": "Left group successfully"}
