from html import escape

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import HTMLResponse

from app.auth.dependencies import get_current_auth_user
from app.database import get_database
from app.schemas import CurrentAuthUser, GroupRequestStatus
from app.services import GroupRequestService, GroupService, StudentService
from app.services.bunk_common import is_reg_no_junior_to, serialize_for_api
from app.utils.group_request_email_actions import decode_group_request_email_action_token
from app.utils.mailer import mailer

router = APIRouter(prefix="/groupRequest", tags=["groupRequest"])


def _render_email_action_page(message: str, *, is_error: bool, status_code: int) -> HTMLResponse:
    title = "Action Failed" if is_error else "Action Completed"
    border_color = "#E94F4F" if is_error else "#47D19D"
    safe_message = escape(message)
    html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width,initial-scale=1">
    <title>{title}</title>
</head>
<body style="margin:0;padding:40px 12px;background:#f4f4f4;font-family:Arial,sans-serif;">
    <div style="max-width:560px;margin:0 auto;background:#ffffff;border:2px solid {border_color};border-radius:10px;padding:24px;">
        <h2 style="margin:0 0 12px 0;color:#000000;">{title}</h2>
        <p style="margin:0;color:#000000;line-height:1.5;">{safe_message}</p>
    </div>
</body>
</html>
"""
    return HTMLResponse(content=html, status_code=status_code)


async def _process_group_request_action(
    *,
    request_id: str,
    action: GroupRequestStatus,
    actor_uid: str,
    background_tasks: BackgroundTasks | None = None,
) -> dict:
    db = get_database()
    group_service = GroupService(db)
    student_service = StudentService(db)
    request_service = GroupRequestService(db)

    if action == GroupRequestStatus.PENDING:
        raise HTTPException(status_code=400, detail="Invalid action")

    group_request = await request_service.get_by_id(request_id)
    if not group_request:
        raise HTTPException(status_code=400, detail="Request doesn't exist")

    group_id = str(group_request["groupId"])
    group = await group_service.get_by_id(group_id)
    if not group:
        raise HTTPException(status_code=400, detail="Group doesn't exist")

    if group["adminUID"] != actor_uid:
        raise HTTPException(status_code=400, detail="You are not the admin")

    student = await student_service.get_by_reg_no(group_request["studentRegNo"])
    if not student:
        raise HTTPException(status_code=400, detail="Student doesn't exist")

    if action == GroupRequestStatus.ACCEPTED:
        if not group_service.is_hostel_compatible(student, group):
            raise HTTPException(status_code=400, detail="Student hostel type does not match this room.")

        admin = await student_service.get_by_uid(group.get("adminUID"))
        if admin and is_reg_no_junior_to(student.get("regNo"), admin.get("regNo")) is True:
            raise HTTPException(status_code=403, detail="Juniors cannot join rooms created by seniors.")

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

        if student.get("email"):
            mail_args = {
                "template_path": "app/templates/emails/request_accepted.html",
                "email_to": student["email"],
                "subject": "Roommate Request Accepted!",
                "context": {
                    "student_name": student.get("name", "Student"),
                    "group_name": group.get("groupName", "the group"),
                },
            }
            if background_tasks is not None:
                background_tasks.add_task(mailer, **mail_args)
            else:
                await mailer(**mail_args)

        return {
            "message": "Request updated successfully",
            "request": {
                "id": request_id,
                "status": GroupRequestStatus.ACCEPTED.value,
                "groupId": updated_group["id"],
                "studentRegNo": student["regNo"],
            },
        }

    updated_request = await request_service.update_status(request_id, action)
    return {"message": "Request updated successfully", "request": serialize_for_api(updated_request)}


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

    admin = await student_service.get_by_uid(group.get("adminUID"))
    if admin and is_reg_no_junior_to(student.get("regNo"), admin.get("regNo")) is True:
        raise HTTPException(status_code=403, detail="Juniors cannot join rooms created by seniors.")

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

    created_request = await request_service.create_request(id, student["regNo"])
    return {"message": "Request sent successfully", "request": serialize_for_api(created_request)}


@router.post("/updateRequest/{id}/{action}")
async def update_request(
    id: str,
    background_tasks: BackgroundTasks,
    action: GroupRequestStatus,
    current_user: CurrentAuthUser = Depends(get_current_auth_user),
):
    return await _process_group_request_action(
        request_id=id,
        action=action,
        actor_uid=current_user.uid,
        background_tasks=background_tasks,
    )


@router.get("/emailAction/{token}", response_class=HTMLResponse)
async def email_action(token: str, background_tasks: BackgroundTasks):
    payload = decode_group_request_email_action_token(token)
    if not payload:
        return _render_email_action_page(
            "This action link is invalid or has expired.",
            is_error=True,
            status_code=400,
        )

    try:
        await _process_group_request_action(
            request_id=payload.request_id,
            action=payload.action,
            actor_uid=payload.admin_uid,
            background_tasks=background_tasks,
        )
    except HTTPException as exc:
        detail = exc.detail if isinstance(exc.detail, str) else "Unable to process this request."
        status_code = exc.status_code if isinstance(exc.status_code, int) else 400
        if status_code < 400:
            status_code = 400
        return _render_email_action_page(detail, is_error=True, status_code=status_code)

    success_message = (
        "Request approved successfully."
        if payload.action == GroupRequestStatus.ACCEPTED
        else "Request removed successfully."
    )
    return _render_email_action_page(success_message, is_error=False, status_code=200)

