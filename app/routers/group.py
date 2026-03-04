from fastapi import APIRouter, Depends, HTTPException, Query, Body

from app.auth.dependencies import get_current_auth_user
from app.database import get_database
from app.schemas import (
    CreateGroupRequest,
    CurrentAuthUser,
    GroupType,
    GroupQueryRequest,
    HostelType,
    UpdateGroupRequest,
)
from app.services import GroupRequestService, GroupService, StudentService
from app.services.bunk_common import (
    LH_BLOCKS,
    LH_ROOM_SIZES,
    MH_BLOCKS,
    MH_ROOM_SIZES,
    is_reg_no_junior_to,
    serialize_for_api,
    verify_blocks,
)
from app.utils.score_combiner import update_total_compatibility

from bson import ObjectId

router = APIRouter(prefix="/group", tags=["group"])

async def _recalculate_group_pending_requests(db, group_id: str):
    group_service = GroupService(db)
    student_service = StudentService(db)
    
    group = await group_service.get_by_id(group_id)
    if not group: return
    
    query_id = ObjectId(group_id) if ObjectId.is_valid(group_id) else group_id
    
    cursor = db["group_requests"].find({
        "groupId": query_id, 
        "status": {"$in": ["PENDING", 0, "Pending"]}
    })
    
    pending_requests = await cursor.to_list(length=None)
    if not pending_requests: return
    
    admin = await student_service.get_by_uid(group.get("adminUID"))
    if not admin: return
    
    member_uids = group.get("studentUids", [])
    if not member_uids:
        member_uids = [admin.get("firebaseUID")]
        
    group_members = await student_service.list_by_uids(member_uids)
    num_members = len(group_members)
    
    avg_clean = sum([float(m.get("cleanliness", 0)) for m in group_members]) / num_members
    avg_social = sum([float(m.get("socialScene", 0)) for m in group_members]) / num_members
    avg_sleep = sum([float(m.get("sleepTime", 0)) for m in group_members]) / num_members
    avg_wake = sum([float(m.get("wakeTime", 0)) for m in group_members]) / num_members
    
    room_profile = {
        **admin,
        "students": group_members,
        "interests": group.get("preferences", admin.get("interests", "")),
        "cleanliness": avg_clean,
        "socialScene": avg_social,
        "sleepTime": avg_sleep,
        "wakeTime": avg_wake
    }
    
    for req in pending_requests:
        student = await student_service.get_by_reg_no(req["studentRegNo"])
        if not student: continue
        
        old_compat = req.get("compatibility") or {}
        breakdown = old_compat.get("breakdown") or {}
        stored_text_score = breakdown.get("interestsScore", 0.5)
        
        match_data = update_total_compatibility(student, room_profile, stored_text_score)
        
        await db["group_requests"].update_one(
            {"_id": req["_id"]},
            {"$set": {"compatibility": match_data}}
        )



def _blocks_for_hostel(hostel_type: str | None) -> list[str]:
    normalized = str(hostel_type or "").upper()
    if normalized == HostelType.MH.value:
        return sorted(MH_BLOCKS)
    if normalized == HostelType.LH.value:
        return sorted(LH_BLOCKS)
    return sorted(MH_BLOCKS | LH_BLOCKS)


def _room_sizes_for_hostel(hostel_type: str | None) -> list[str]:
    normalized = str(hostel_type or "").upper()
    if normalized == HostelType.MH.value:
        return [str(value) for value in MH_ROOM_SIZES]
    if normalized == HostelType.LH.value:
        return [str(value) for value in LH_ROOM_SIZES]
    return [str(value) for value in sorted(set(MH_ROOM_SIZES) | set(LH_ROOM_SIZES))]


def _parse_multi_query_values(values: list[str] | None) -> list[str]:
    if not values:
        return []
    parsed: list[str] = []
    seen: set[str] = set()
    for value in values:
        for part in str(value or "").split(","):
            text = part.strip()
            if not text:
                continue
            key = text.lower()
            if key in seen:
                continue
            seen.add(key)
            parsed.append(text)
    return parsed


@router.get("/listGroups")
async def list_groups(
    offset: int = Query(0),
    limit: int = Query(20),
    page: int = Query(1),
    pageSize: int = Query(20),
    search: str | None = Query(None),
    sortBy: str | None = Query(None),
    sortOrder: str | None = Query(None),
    type: str | None = Query(None),
    groupSize: str | None = Query(None),
    groupSizes: list[str] | None = Query(None),
    block1: str | None = Query(None),
    block2: str | None = Query(None),
    block3: str | None = Query(None),
    blocks: list[str] | None = Query(None),
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

    query_payload = {
        "offset": offset,
        "limit": limit,
        "page": page,
        "pageSize": pageSize,
        "search": search,
        "sortBy": sortBy,
        "type": type,
        "groupSize": groupSize,
        "groupSizes": _parse_multi_query_values(groupSizes),
        "block1": block1,
        "block2": block2,
        "block3": block3,
        "blocks": _parse_multi_query_values(blocks),
        "vacancy": vacancy,
        "minCGPA": minCGPA,
        "maxCGPA": maxCGPA,
    }
    if sortOrder is not None:
        query_payload["sortOrder"] = sortOrder

    query = GroupQueryRequest(**query_payload)

    result = await group_service.list_groups_for_student(student, query)
    groups = result.get("groups", [])
    return {
        "total": result.get("totalCount", len(groups)),
        "totalCount": result.get("totalCount", len(groups)),
        "page": result.get("page", page),
        "pageSize": result.get("pageSize", pageSize),
        "totalPages": result.get("totalPages", 1),
        "hasNextPage": result.get("hasNextPage", False),
        "hasPrevPage": result.get("hasPrevPage", False),
        "message": "Groups fetched successfully.",
        "groups": serialize_for_api(groups),
        "filterOptions": {
            "hostelType": student.get("hostelType"),
            "roomTypes": [GroupType.AC.value, GroupType.NON_AC.value],
            "roomSizes": _room_sizes_for_hostel(student.get("hostelType")),
            "blocks": _blocks_for_hostel(student.get("hostelType")),
        },
    }


@router.post("/createGroup")
async def create_group(
    payload: CreateGroupRequest,
    current_user: CurrentAuthUser = Depends(get_current_auth_user),
):
    db = get_database()
    student_service = StudentService(db)
    group_service = GroupService(db)
    request_service = GroupRequestService(db)

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
    if student.get("regNo"):
        await request_service.delete_all_for_student(student["regNo"])

    return {"message": "Group created successfully.", "group": serialize_for_api(group)}


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
    
    await _recalculate_group_pending_requests(db, updated_group["id"])
    
    return {"message": "Group updated successfully.", "group": serialize_for_api(updated_group)}


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

    try:
        if await group_service.is_full(group):
            raise HTTPException(status_code=400, detail="Group is full")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

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
    request_service = GroupRequestService(db)

    student = await student_service.get_by_uid(current_user.uid)
    if not student:
        raise HTTPException(status_code=400, detail="Student not found")
    if not student.get("hostelType"):
        raise HTTPException(status_code=400, detail="Student has not selected a hostel type.")

    existing_group = await group_service.get_any_group_for_student_uid(current_user.uid)
    if existing_group:
        if not student.get("groupId"):
            await student_service.set_group(current_user.uid, existing_group["id"])
        if student.get("regNo"):
            await request_service.delete_all_for_student(student["regNo"])
        raise HTTPException(status_code=400, detail="You are already in a group")

    group = await group_service.get_by_group_code(code)
    if not group:
        raise HTTPException(status_code=400, detail="Group does not exist")
    if not group_service.is_hostel_compatible(student, group):
        raise HTTPException(status_code=403, detail="You can only join rooms from your own hostel type.")

    admin = await student_service.get_by_uid(group.get("adminUID"))
    if admin and is_reg_no_junior_to(student.get("regNo"), admin.get("regNo")) is True:
        raise HTTPException(status_code=403, detail="Juniors cannot join rooms created by seniors.")

    group_student_uids = group_service.get_student_uids(group)
    if current_user.uid == group["adminUID"] or current_user.uid in group_student_uids:
        raise HTTPException(status_code=400, detail="You have already joined this group")

    if await group_service.is_group_code_expired(group):
        raise HTTPException(status_code=400, detail="Group code has expired")

    try:
        if await group_service.is_full(group):
            raise HTTPException(status_code=400, detail="Group is full")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    try:
        updated_group = await group_service.add_student(group, current_user.uid)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    await student_service.set_group(current_user.uid, updated_group["id"])
    if student.get("regNo"):
        await request_service.delete_all_for_student(student["regNo"])

    await _recalculate_group_pending_requests(db, updated_group["id"])

    return {"message": "Joined group successfully", "group": serialize_for_api(updated_group)}


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

    await _recalculate_group_pending_requests(db, group["id"])

    return {"message": "Left group successfully"}


@router.post("/removeMember")
async def remove_member_from_group(
    payload: dict = Body(...),
    current_user: CurrentAuthUser = Depends(get_current_auth_user),
):
    db = get_database()
    student_service = StudentService(db)
    group_service = GroupService(db)

    group_id = payload.get("groupId")
    member_uid = payload.get("memberUID")
    if not group_id or not member_uid:
        raise HTTPException(status_code=400, detail="groupId and memberUID are required")

    group = await group_service.get_by_id(group_id)
    if not group:
        raise HTTPException(status_code=400, detail="Group does not exist")

    if group["adminUID"] != current_user.uid:
        raise HTTPException(status_code=403, detail="Only the group admin can remove members")

    if member_uid == current_user.uid:
        raise HTTPException(status_code=400, detail="Admin cannot remove themselves")

    if member_uid not in group_service.get_student_uids(group):
        raise HTTPException(status_code=404, detail="Member not found in group")

    updated_group = await group_service.remove_student(group, member_uid)
    await student_service.set_group(member_uid, None)

    await _recalculate_group_pending_requests(db, updated_group["id"])

    return {
        "message": "Member removed from group successfully",
        "group": serialize_for_api(updated_group),
    }
