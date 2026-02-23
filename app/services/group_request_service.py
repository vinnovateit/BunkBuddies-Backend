from __future__ import annotations

from typing import Optional

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.schemas import GroupRequestStatus
from app.services.bunk_common import now_utc, object_id_from_str


class GroupRequestService:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.collection = db["group_requests"]

    async def get_existing(self, group_id: str, student_reg_no: str) -> Optional[dict]:
        oid = object_id_from_str(group_id)
        if not oid:
            return None
        return await self.collection.find_one({"groupId": oid, "studentRegNo": student_reg_no})

    async def create_request(self, group_id: str, student_reg_no: str) -> dict:
        oid = object_id_from_str(group_id)
        payload = {
            "status": GroupRequestStatus.PENDING.value,
            "groupId": oid,
            "studentRegNo": student_reg_no,
            "createdAt": now_utc(),
        }
        result = await self.collection.insert_one(payload)
        payload["id"] = str(result.inserted_id)
        payload["_id"] = result.inserted_id
        return payload

    async def get_by_id(self, request_id: str) -> Optional[dict]:
        oid = object_id_from_str(request_id)
        if not oid:
            return None
        req = await self.collection.find_one({"_id": oid})
        if req:
            req["id"] = str(req["_id"])
        return req

    async def update_status(self, request_id: str, status: GroupRequestStatus) -> Optional[dict]:
        oid = object_id_from_str(request_id)
        if not oid:
            return None

        await self.collection.update_one(
            {"_id": oid},
            {"$set": {"status": status.value}},
        )
        req = await self.collection.find_one({"_id": oid})
        if req:
            req["id"] = str(req["_id"])
        return req

    async def delete_all_for_student(self, student_reg_no: str) -> None:
        await self.collection.delete_many({"studentRegNo": student_reg_no})

    async def delete_for_group(self, group_id: str) -> None:
        oid = object_id_from_str(group_id)
        if not oid:
            return
        await self.collection.delete_many({"groupId": oid})

    async def list_unsent_pending(self, *, limit: int = 5000) -> list[dict]:
        query = {
            "status": GroupRequestStatus.PENDING.value,
            "$or": [
                {"adminDigestSentAt": {"$exists": False}},
                {"adminDigestSentAt": None},
            ],
        }
        cursor = self.collection.find(query).sort([("createdAt", -1), ("_id", -1)])
        requests = await cursor.to_list(length=max(limit, 1))
        for req in requests:
            req["id"] = str(req["_id"])
        return requests

    async def mark_digest_sent(self, request_object_ids: list[ObjectId]) -> None:
        if not request_object_ids:
            return
        await self.collection.update_many(
            {"_id": {"$in": request_object_ids}},
            {"$set": {"adminDigestSentAt": now_utc()}},
        )
