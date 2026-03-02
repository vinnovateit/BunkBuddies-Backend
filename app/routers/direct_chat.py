import json
from datetime import datetime, timezone
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson import ObjectId 

from app.database import get_database
from app.services.student_service import StudentService

router = APIRouter(
    prefix="/dm",
    tags=["Direct Messaging"]
)

async def can_users_chat(db: AsyncIOMotorDatabase, reg_no_1: str, reg_no_2: str) -> bool:
    student_service = StudentService(db)
    s1 = await student_service.get_by_reg_no(reg_no_1)
    s2 = await student_service.get_by_reg_no(reg_no_2)

    if not s1 or not s2: return False
    uid1, uid2 = s1.get("firebaseUID"), s2.get("firebaseUID")

    async def check_admin_requester(admin_uid: str, requester_reg_no: str) -> bool:
        admin_groups = await db["groups"].find({"adminUID": admin_uid}).to_list(length=100)
        group_ids = [g["_id"] for g in admin_groups]
        if not group_ids: return False
        
        group_ids_str = [str(gid) for gid in group_ids]
        
        request = await db["group_requests"].find_one({
            "$or": [
                {"groupId": {"$in": group_ids}, "studentRegNo": requester_reg_no, "status": "PENDING"},
                {"groupId": {"$in": group_ids_str}, "studentRegNo": requester_reg_no, "status": "PENDING"}
            ]
        })
        return bool(request)

    if await check_admin_requester(uid1, reg_no_2): return True
    if await check_admin_requester(uid2, reg_no_1): return True
    return False

@router.get("/contacts/{reg_no}")
async def get_dm_contacts(reg_no: str, db: AsyncIOMotorDatabase = Depends(get_database)):
    student_service = StudentService(db)
    me = await student_service.get_by_reg_no(reg_no)
    if not me: raise HTTPException(status_code=404, detail="Student not found")

    my_uid = me.get("firebaseUID")
    contacts_dict = {}

    unread_pipeline = [
        {"$match": {"receiverRegNo": reg_no, "read": False}},
        {"$group": {"_id": "$senderRegNo", "count": {"$sum": 1}}}
    ]
    unread_results = await db["direct_messages"].aggregate(unread_pipeline).to_list(length=100)
    unread_counts = {item["_id"]: item["count"] for item in unread_results}

    def add_contact(student, role):
        s_reg = student["regNo"]
        if s_reg not in contacts_dict:
            contacts_dict[s_reg] = {
                "regNo": s_reg, 
                "name": student["name"], 
                "role": role,
                "unread": unread_counts.get(s_reg, 0)
            }

    my_groups = await db["groups"].find({"adminUID": my_uid}).to_list(length=100)
    my_group_ids = [g["_id"] for g in my_groups]
    my_group_ids_str = [str(gid) for gid in my_group_ids]
    
    if my_group_ids:
        incoming_reqs = await db["group_requests"].find({
            "$or": [{"groupId": {"$in": my_group_ids}}, {"groupId": {"$in": my_group_ids_str}}],
            "status": "PENDING"
        }).to_list(length=1000)
        
        requester_regs = [req["studentRegNo"] for req in incoming_reqs]
        if requester_regs:
            requesters = await db["students"].find({"regNo": {"$in": requester_regs}}).to_list(length=1000)
            for student in requesters: add_contact(student, "Applicant")

    outgoing_reqs = await db["group_requests"].find({"studentRegNo": reg_no, "status": "PENDING"}).to_list(length=1000)
    target_group_ids = [req["groupId"] for req in outgoing_reqs]
    
    valid_object_ids = []
    for gid in target_group_ids:
        if isinstance(gid, ObjectId): valid_object_ids.append(gid)
        elif isinstance(gid, str) and ObjectId.is_valid(gid): valid_object_ids.append(ObjectId(gid))

    if valid_object_ids:
        target_groups = await db["groups"].find({"_id": {"$in": valid_object_ids}}).to_list(length=100)
        admin_uids = [g["adminUID"] for g in target_groups]
        if admin_uids:
            admins = await db["students"].find({"firebaseUID": {"$in": admin_uids}}).to_list(length=100)
            for student in admins: add_contact(student, "Room Admin")

    return list(contacts_dict.values())

class DMConnectionManager:
    def __init__(self):
        self.active_users: dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, reg_no: str):
        await websocket.accept()
        self.active_users[reg_no] = websocket

    def disconnect(self, reg_no: str):
        if reg_no in self.active_users:
            del self.active_users[reg_no]

    async def send_personal_message(self, message: dict, receiver_reg_no: str):
        if receiver_reg_no in self.active_users:
            await self.active_users[receiver_reg_no].send_json(message)

dm_manager = DMConnectionManager()

@router.get("/history/{my_reg_no}/{target_reg_no}")
async def get_chat_history(
    my_reg_no: str, 
    target_reg_no: str, 
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    if not await can_users_chat(db, my_reg_no, target_reg_no):
        raise HTTPException(status_code=403, detail="Permission denied.")

    await db["direct_messages"].update_many(
        {"senderRegNo": target_reg_no, "receiverRegNo": my_reg_no, "read": False},
        {"$set": {"read": True}}
    )

    query = {
        "$or": [
            {"senderRegNo": my_reg_no, "receiverRegNo": target_reg_no},
            {"senderRegNo": target_reg_no, "receiverRegNo": my_reg_no}
        ]
    }
    
    cursor = db["direct_messages"].find(query).sort("timestamp", 1)
    messages = await cursor.to_list(length=1000)
    
    for msg in messages:
        msg["id"] = str(msg["_id"])
        del msg["_id"]
        if "timestamp" in msg and msg["timestamp"].tzinfo is None:
            msg["timestamp"] = msg["timestamp"].replace(tzinfo=timezone.utc)
        
    return messages

@router.websocket("/ws/{my_reg_no}")
async def dm_websocket_endpoint(
    websocket: WebSocket, 
    my_reg_no: str, 
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    if my_reg_no in dm_manager.active_users:
        dm_manager.disconnect(my_reg_no)

    await dm_manager.connect(websocket, my_reg_no)

    try:
        while True:
            raw_data = await websocket.receive_text()
            data = json.loads(raw_data)
            
            target_reg_no = data.get("targetRegNo")
            text_data = data.get("message")
            
            if not target_reg_no or not text_data:
                continue

            if not await can_users_chat(db, my_reg_no, target_reg_no):
                await websocket.send_json({"type": "error", "message": f"Cannot message {target_reg_no}"})
                continue

            timestamp = datetime.now(timezone.utc)
            
            db_message = {
                "senderRegNo": my_reg_no,
                "receiverRegNo": target_reg_no,
                "message": text_data,
                "timestamp": timestamp,
                "read": False
            }
            result = await db["direct_messages"].insert_one(db_message)
            
            broadcast_payload = {
                "id": str(result.inserted_id),
                "type": "chat",
                "senderRegNo": my_reg_no,
                "receiverRegNo": target_reg_no,
                "message": text_data,
                "timestamp": timestamp.isoformat()
            }
            
            await dm_manager.send_personal_message(broadcast_payload, target_reg_no)
            await websocket.send_json(broadcast_payload) 
            
    except WebSocketDisconnect:
        dm_manager.disconnect(my_reg_no)
    except json.JSONDecodeError:
        pass