from __future__ import annotations

from datetime import timedelta
from typing import Optional

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.schemas import GroupQueryRequest, GroupRequestStatus
from app.services.bunk_common import (
    generate_group_code,
    now_utc,
    object_id_from_str,
    size_to_capacity,
)
from app.services.student_service import StudentService


class GroupService:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.collection = db["groups"]
        self.student_service = StudentService(db)
        self.request_collection = db["group_requests"]

    async def get_by_id(self, group_id: str) -> Optional[dict]:
        oid = object_id_from_str(group_id)
        if not oid:
            return None
        group = await self.collection.find_one({"_id": oid})
        if group:
            group["id"] = str(group["_id"])
        return group

    async def get_by_group_code(self, code: str) -> Optional[dict]:
        group = await self.collection.find_one({"groupCode": code})
        if group:
            group["id"] = str(group["_id"])
        return group

    async def get_group_for_student_uid(self, uid: str) -> Optional[dict]:
        student = await self.student_service.get_by_uid(uid)
        if not student or not student.get("groupId"):
            return None
        return await self.get_by_id(student["groupId"])

    async def create_group(self, data: dict) -> dict:
        payload = {
            **data,
            "groupCode": None,
            "createdAt": now_utc(),
            "studentUids": [data["adminUID"]],
        }
        result = await self.collection.insert_one(payload)
        payload["id"] = str(result.inserted_id)
        payload["_id"] = result.inserted_id
        return payload

    async def update_group(self, group_id: str, update_data: dict) -> Optional[dict]:
        oid = object_id_from_str(group_id)
        if not oid:
            return None
        if update_data:
            await self.collection.update_one({"_id": oid}, {"$set": update_data})
        group = await self.collection.find_one({"_id": oid})
        if group:
            group["id"] = str(group["_id"])
        return group

    async def delete_group(self, group_id: str) -> bool:
        oid = object_id_from_str(group_id)
        if not oid:
            return False
        result = await self.collection.delete_one({"_id": oid})
        return result.deleted_count > 0

    async def is_full(self, group: dict) -> bool:
        return len(group.get("studentUids", [])) >= size_to_capacity(group["groupSize"])

    async def add_student(self, group: dict, student_uid: str) -> dict:
        await self.collection.update_one(
            {"_id": group["_id"]},
            {"$addToSet": {"studentUids": student_uid}},
        )
        refreshed = await self.collection.find_one({"_id": group["_id"]})
        refreshed["id"] = str(refreshed["_id"])
        return refreshed

    async def remove_student(self, group: dict, student_uid: str) -> dict:
        await self.collection.update_one(
            {"_id": group["_id"]},
            {"$pull": {"studentUids": student_uid}},
        )
        refreshed = await self.collection.find_one({"_id": group["_id"]})
        refreshed["id"] = str(refreshed["_id"])
        return refreshed

    async def generate_code(self, group: dict) -> str:
        code = await generate_group_code(self.collection)
        await self.collection.update_one(
            {"_id": group["_id"]},
            {"$set": {"groupCode": code, "createdAt": now_utc()}},
        )
        return code

    async def is_group_code_expired(self, group: dict) -> bool:
        created_at = group.get("createdAt")
        if not created_at:
            return True
        return now_utc() - created_at > timedelta(minutes=15)

    async def list_groups_for_student(self, student: dict, query: GroupQueryRequest) -> list[dict]:
        mongo_query = {"hostelType": student["hostelType"]}

        if query.type:
            mongo_query["type"] = query.type.value
        if query.groupSize:
            mongo_query["groupSize"] = query.groupSize.value
        if query.block1:
            mongo_query["$or"] = [{"block1": query.block1}, {"block2": query.block1}, {"block3": query.block1}]
        if query.block2:
            mongo_query.setdefault("$and", []).append(
                {"$or": [{"block1": query.block2}, {"block2": query.block2}, {"block3": query.block2}]}
            )
        if query.block3:
            mongo_query.setdefault("$and", []).append(
                {"$or": [{"block1": query.block3}, {"block2": query.block3}, {"block3": query.block3}]}
            )

        groups = await self.collection.find(mongo_query).skip(query.offset).limit(query.limit).to_list(length=query.limit)

        hydrated: list[dict] = []
        for group in groups:
            students = await self.student_service.list_by_uids(group.get("studentUids", []))
            admin = next((s for s in students if s.get("firebaseUID") == group.get("adminUID")), None)

            if query.vacancy is not None:
                capacity = size_to_capacity(group["groupSize"])
                if capacity - len(students) < query.vacancy:
                    continue

            if query.minCGPA is not None and (not admin or admin.get("CGPA") is None or admin["CGPA"] < query.minCGPA):
                continue
            if query.maxCGPA is not None and (not admin or admin.get("CGPA") is None or admin["CGPA"] > query.maxCGPA):
                continue

            group["id"] = str(group["_id"])
            group["students"] = students
            group["adminCGPA"] = admin.get("CGPA") if admin else None
            hydrated.append(group)

        hydrated.sort(
            key=lambda g: (
                -(g["adminCGPA"] if g["adminCGPA"] is not None else -1),
            )
        )
        return hydrated

    async def get_pending_requests_for_admin(self, admin_uid: str) -> list[dict]:
        groups = await self.collection.find({"adminUID": admin_uid}).to_list(length=500)
        if not groups:
            return []

        group_ids = [g["_id"] for g in groups]
        requests = await self.request_collection.find(
            {"groupId": {"$in": group_ids}, "status": GroupRequestStatus.PENDING.value}
        ).to_list(length=1000)

        student_reg_nos = [r["studentRegNo"] for r in requests]
        students = await self.student_service.collection.find({"regNo": {"$in": student_reg_nos}}).to_list(length=1000)
        student_map = {s["regNo"]: s for s in students}
        group_map = {g["_id"]: g for g in groups}

        enriched = []
        for req in requests:
            grp = group_map.get(req["groupId"])
            std = student_map.get(req["studentRegNo"])
            if not grp or not std:
                continue
            req["id"] = str(req["_id"])
            req["group"] = {**grp, "id": str(grp["_id"])}
            req["student"] = std
            enriched.append(req)

        return enriched
