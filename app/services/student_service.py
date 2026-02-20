from __future__ import annotations

from typing import Optional

from motor.motor_asyncio import AsyncIOMotorDatabase


class StudentService:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.collection = db["students"]

    async def get_by_reg_no(self, reg_no: str) -> Optional[dict]:
        return await self.collection.find_one({"regNo": reg_no})

    async def get_by_uid(self, firebase_uid: str) -> Optional[dict]:
        return await self.collection.find_one({"firebaseUID": firebase_uid})

    async def create_student(self, data: dict) -> dict:
        await self.collection.insert_one(data)
        return data

    async def update_by_uid(self, firebase_uid: str, update_data: dict) -> Optional[dict]:
        if not update_data:
            return await self.get_by_uid(firebase_uid)

        await self.collection.update_one(
            {"firebaseUID": firebase_uid},
            {"$set": update_data},
        )
        return await self.get_by_uid(firebase_uid)

    async def set_group(self, firebase_uid: str, group_id: str | None) -> None:
        await self.collection.update_one(
            {"firebaseUID": firebase_uid},
            {"$set": {"groupId": group_id}},
        )

    async def clear_group_for_uids(self, student_uids: list[str]) -> None:
        if not student_uids:
            return
        await self.collection.update_many(
            {"firebaseUID": {"$in": student_uids}},
            {"$set": {"groupId": None}},
        )

    async def list_by_uids(self, student_uids: list[str]) -> list[dict]:
        if not student_uids:
            return []
        return await self.collection.find({"firebaseUID": {"$in": student_uids}}).to_list(length=100)
