from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.schemas import GroupQueryRequest, GroupRequestStatus
from app.services.bunk_common import (
    generate_group_code,
    is_reg_no_junior_to,
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

    @staticmethod
    def get_student_uids(group: dict) -> list[str]:
        raw = group.get("studentUids")
        if isinstance(raw, list):
            return [uid for uid in raw if isinstance(uid, str) and uid.strip()]
        if isinstance(raw, str) and raw.strip():
            return [raw.strip()]
        return []

    @staticmethod
    def is_hostel_compatible(student: dict, group: dict) -> bool:
        student_hostel = student.get("hostelType")
        group_hostel = group.get("hostelType")
        if not student_hostel or not group_hostel:
            return False
        return student_hostel == group_hostel

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

    async def get_any_group_for_student_uid(self, uid: str) -> Optional[dict]:
        if not uid:
            return None

        group = await self.collection.find_one(
            {
                "$or": [
                    {"adminUID": uid},
                    {"studentUids": uid},
                ],
            }
        )
        if group:
            group["id"] = str(group["_id"])
        return group

    async def create_group(self, data: dict) -> dict:
        payload = {
            **data,
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
        return len(self.get_student_uids(group)) >= size_to_capacity(group.get("groupSize"))

    async def add_student(self, group: dict, student_uid: str) -> dict:
        normalized_uids = self.get_student_uids(group)
        await self.collection.update_one(
            {"_id": group["_id"]},
            {"$set": {"studentUids": normalized_uids}},
        )

        await self.collection.update_one(
            {"_id": group["_id"]},
            {"$addToSet": {"studentUids": student_uid}},
        )
        refreshed = await self.collection.find_one({"_id": group["_id"]})
        if not refreshed:
            raise ValueError("Group no longer exists")
        refreshed["id"] = str(refreshed["_id"])
        return refreshed

    async def remove_student(self, group: dict, student_uid: str) -> dict:
        normalized_uids = self.get_student_uids(group)
        await self.collection.update_one(
            {"_id": group["_id"]},
            {"$set": {"studentUids": normalized_uids}},
        )

        await self.collection.update_one(
            {"_id": group["_id"]},
            {"$pull": {"studentUids": student_uid}},
        )
        refreshed = await self.collection.find_one({"_id": group["_id"]})
        if not refreshed:
            raise ValueError("Group no longer exists")
        refreshed["id"] = str(refreshed["_id"])
        return refreshed

    async def generate_code(self, group: dict) -> str:
        existing_code = group.get("groupCode")
        if existing_code and not await self.is_group_code_expired(group):
            return existing_code

        code = await generate_group_code(self.collection)
        await self.collection.update_one(
            {"_id": group["_id"]},
            {"$set": {"groupCode": code, "createdAt": now_utc()}},
        )
        return code

    async def is_group_code_expired(self, group: dict) -> bool:
        if not group.get("groupCode"):
            return True

        created_at = group.get("createdAt")
        if not created_at:
            return True

        if isinstance(created_at, str):
            try:
                created_at = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            except ValueError:
                return True

        if not isinstance(created_at, datetime):
            return True

        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)

        current_time = now_utc()
        if current_time.tzinfo is None:
            current_time = current_time.replace(tzinfo=timezone.utc)

        return current_time - created_at > timedelta(minutes=15)

    async def list_groups_for_student(self, student: dict, query: GroupQueryRequest) -> dict:
        mongo_query = {"hostelType": student["hostelType"]}
        student_uid = student.get("firebaseUID")
        student_group_id = object_id_from_str(student.get("groupId", ""))

        if student_uid:
            mongo_query["adminUID"] = {"$ne": student_uid}
            mongo_query["studentUids"] = {"$ne": student_uid}
        if student_group_id:
            mongo_query["_id"] = {"$ne": student_group_id}

        if query.type:
            mongo_query["type"] = query.type.value

        selected_group_sizes: list[str] = []
        if query.groupSize:
            selected_group_sizes.append(query.groupSize.value)
        if query.groupSizes:
            selected_group_sizes.extend(size.value for size in query.groupSizes)
        if selected_group_sizes:
            mongo_query["groupSize"] = {"$in": list(dict.fromkeys(selected_group_sizes))}

        selected_blocks: list[str] = []
        selected_blocks.extend(
            str(value).strip() for value in [query.block1, query.block2, query.block3] if str(value or "").strip()
        )
        if query.blocks:
            selected_blocks.extend(str(value).strip() for value in query.blocks if str(value or "").strip())
        if selected_blocks:
            block_values = list(dict.fromkeys(selected_blocks))
            mongo_query.setdefault("$and", []).append(
                {"$or": [{"block1": {"$in": block_values}}, {"block2": {"$in": block_values}}, {"block3": {"$in": block_values}}]}
            )

        groups = await self.collection.find(mongo_query).to_list(length=1000)
        search_text = str(query.search or "").strip().lower()

        hydrated: list[dict] = []
        for group in groups:
            if not self.is_hostel_compatible(student, group):
                continue

            if student_uid:
                if group.get("adminUID") == student_uid or student_uid in self.get_student_uids(group):
                    continue
            if student_group_id and group.get("_id") == student_group_id:
                continue

            students = await self.student_service.list_by_uids(self.get_student_uids(group))
            admin = next((s for s in students if s.get("firebaseUID") == group.get("adminUID")), None)
            if not admin and group.get("adminUID"):
                admin = await self.student_service.get_by_uid(group["adminUID"])

            # Juniors should not see rooms created by seniors.
            if admin and is_reg_no_junior_to(student.get("regNo"), admin.get("regNo")) is True:
                continue

            capacity = size_to_capacity(group["groupSize"])
            available_beds = max(capacity - len(students), 0)

            if query.vacancy is not None:
                if available_beds < query.vacancy:
                    continue

            if query.minCGPA is not None and (not admin or admin.get("CGPA") is None or admin["CGPA"] < query.minCGPA):
                continue
            if query.maxCGPA is not None and (not admin or admin.get("CGPA") is None or admin["CGPA"] > query.maxCGPA):
                continue

            if search_text:
                searchable_parts = [
                    str(group.get("groupName") or ""),
                    str(admin.get("name") if admin else ""),
                    str(admin.get("regNo") if admin else ""),
                ]
                searchable_parts.extend(str(member.get("name") or "") for member in students)
                searchable_parts.extend(str(member.get("regNo") or "") for member in students)
                searchable_text = " ".join(searchable_parts).lower()
                if search_text not in searchable_text:
                    continue

            group["id"] = str(group["_id"])
            group["memberCount"] = len(students)
            group["adminCGPA"] = admin.get("CGPA") if admin else None
            group["adminName"] = admin.get("name") if admin else None
            group["adminRegNo"] = admin.get("regNo") if admin else None
            group["availableBeds"] = available_beds
            hydrated.append(group)

        sort_by = query.sortBy.value if query.sortBy else ""
        sort_order = query.sortOrder.value if query.sortOrder else "desc"
        reverse = sort_order != "asc"

        if sort_by == "vacancy":
            hydrated.sort(
                key=lambda g: (
                    g["availableBeds"] if g.get("availableBeds") is not None else -1,
                    str(g.get("groupName") or "").lower(),
                ),
                reverse=reverse,
            )
        elif sort_by == "cgpa":
            hydrated.sort(
                key=lambda g: (
                    g["adminCGPA"] if g.get("adminCGPA") is not None else -1,
                    str(g.get("groupName") or "").lower(),
                ),
                reverse=reverse,
            )
        else:
            hydrated.sort(
                key=lambda g: (
                    -(g["adminCGPA"] if g["adminCGPA"] is not None else -1),
                    str(g.get("groupName") or "").lower(),
                )
            )

        total_count = len(hydrated)
        page = max(query.page, 1)
        page_size = max(query.pageSize, 1)
        if query.page == 1 and query.pageSize == 20 and (query.offset > 0 or query.limit != 20):
            page_size = max(query.limit, 1)
            page = query.offset // page_size + 1
            start = query.offset
        else:
            start = (page - 1) * page_size
        end = start + page_size

        total_pages = max((total_count + page_size - 1) // page_size, 1)
        safe_page = min(page, total_pages)
        if safe_page != page and not (query.page == 1 and query.pageSize == 20 and (query.offset > 0 or query.limit != 20)):
            start = (safe_page - 1) * page_size
            end = start + page_size
        paged_groups = hydrated[start:end]

        return {
            "groups": paged_groups,
            "totalCount": total_count,
            "page": safe_page,
            "pageSize": page_size,
            "totalPages": total_pages,
            "hasPrevPage": safe_page > 1,
            "hasNextPage": safe_page < total_pages,
        }

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
