from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from urllib.parse import quote

from app.auth.jwt import create_access_token, decode_access_token
from app.schemas import GroupRequestStatus

EMAIL_ACTION_TOKEN_TYPE = "group_request_email_action"
EMAIL_ACTION_TOKEN_EXPIRY_HOURS = 48


@dataclass(frozen=True)
class GroupRequestEmailActionPayload:
    request_id: str
    admin_uid: str
    action: GroupRequestStatus


def build_group_request_email_action_url(
    *,
    base_url: str,
    request_id: str,
    admin_uid: str,
    action: GroupRequestStatus,
) -> str:
    token = create_access_token(
        {
            "typ": EMAIL_ACTION_TOKEN_TYPE,
            "request_id": request_id,
            "admin_uid": admin_uid,
            "action": action.value,
        },
        expires_delta=timedelta(hours=EMAIL_ACTION_TOKEN_EXPIRY_HOURS),
    )
    return f"{base_url.rstrip('/')}/groupRequest/emailAction/{quote(token, safe='')}"


def decode_group_request_email_action_token(token: str) -> GroupRequestEmailActionPayload | None:
    payload = decode_access_token(token)
    if not payload or payload.get("typ") != EMAIL_ACTION_TOKEN_TYPE:
        return None

    request_id = payload.get("request_id")
    admin_uid = payload.get("admin_uid")
    action_raw = payload.get("action")
    if not isinstance(request_id, str) or not isinstance(admin_uid, str) or not isinstance(action_raw, str):
        return None

    try:
        action = GroupRequestStatus(action_raw)
    except ValueError:
        return None

    if action not in (GroupRequestStatus.ACCEPTED, GroupRequestStatus.REJECTED):
        return None

    return GroupRequestEmailActionPayload(
        request_id=request_id,
        admin_uid=admin_uid,
        action=action,
    )
