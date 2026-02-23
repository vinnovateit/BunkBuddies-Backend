from __future__ import annotations

import asyncio
import logging
from collections import defaultdict

from bson import ObjectId

from app.database import get_database
from app.services import GroupRequestService
from app.utils.mailer import mailer
from config import settings

logger = logging.getLogger(__name__)


async def send_group_request_digest_once() -> int:
    db = get_database()
    if db is None:
        return 0

    request_service = GroupRequestService(db)
    unsent_requests = await request_service.list_unsent_pending(limit=10000)
    if not unsent_requests:
        return 0

    group_ids = list(
        {
            group_id
            for group_id in (req.get("groupId") for req in unsent_requests)
            if isinstance(group_id, ObjectId)
        }
    )
    if not group_ids:
        return 0

    groups = await db["groups"].find({"_id": {"$in": group_ids}}).to_list(length=len(group_ids))
    group_map = {group["_id"]: group for group in groups}

    by_admin: dict[str, list[tuple[dict, dict]]] = defaultdict(list)
    requester_reg_nos: set[str] = set()
    admin_uids: set[str] = set()

    for req in unsent_requests:
        group = group_map.get(req.get("groupId"))
        if not group:
            continue
        admin_uid = group.get("adminUID")
        if not isinstance(admin_uid, str) or not admin_uid.strip():
            continue
        by_admin[admin_uid].append((req, group))
        admin_uids.add(admin_uid)

        reg_no = req.get("studentRegNo")
        if isinstance(reg_no, str) and reg_no.strip():
            requester_reg_nos.add(reg_no)

    if not by_admin:
        return 0

    admin_students = await db["students"].find({"firebaseUID": {"$in": list(admin_uids)}}).to_list(length=len(admin_uids))
    admin_map = {
        student["firebaseUID"]: student
        for student in admin_students
        if isinstance(student.get("firebaseUID"), str)
    }

    requester_students = await db["students"].find({"regNo": {"$in": list(requester_reg_nos)}}).to_list(
        length=max(len(requester_reg_nos), 1)
    )
    requester_map = {
        student["regNo"]: student
        for student in requester_students
        if isinstance(student.get("regNo"), str)
    }

    batch_size = max(settings.group_request_digest_batch_size, 1)
    sent_requests = 0

    for admin_uid, rows in by_admin.items():
        admin = admin_map.get(admin_uid)
        if not admin:
            continue
        admin_email = admin.get("email")
        if not isinstance(admin_email, str) or not admin_email.strip():
            continue

        selected_rows = rows[:batch_size]
        digest_rows: list[dict] = []
        sent_request_ids: list[ObjectId] = []

        for req, group in selected_rows:
            req_oid = req.get("_id")
            if not isinstance(req_oid, ObjectId):
                continue
            sent_request_ids.append(req_oid)

            reg_no = req.get("studentRegNo", "")
            requester = requester_map.get(reg_no, {})
            digest_rows.append(
                {
                    "sender_name": requester.get("name", "A Student"),
                    "sender_reg": reg_no,
                    "group_name": group.get("groupName", "your group"),
                }
            )

        if not digest_rows or not sent_request_ids:
            continue

        total_request_count = len(rows)
        subject = f"{total_request_count} New Roommate Requests"

        try:
            await mailer(
                template_path="app/templates/emails/request_received.html",
                email_to=admin_email,
                subject=subject,
                context={
                    "admin_name": admin.get("name", "Admin"),
                    "request_count": total_request_count,
                    "requests": digest_rows,
                },
            )
        except Exception:
            logger.exception("Failed to send group request digest for admin uid=%s", admin_uid)
            continue

        await request_service.mark_digest_sent(sent_request_ids)
        sent_requests += len(sent_request_ids)

    return sent_requests


async def run_group_request_digest_scheduler() -> None:
    interval_seconds = max(settings.group_request_digest_interval_hours, 1) * 3600

    while True:
        try:
            await send_group_request_digest_once()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Group request digest scheduler cycle failed")

        await asyncio.sleep(interval_seconds)
