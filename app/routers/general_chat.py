import json
from datetime import datetime, timezone
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.database import get_database
from app.services.student_service import StudentService

router = APIRouter(prefix="/generalChat", tags=["generalChat"])

class Room:
    def __init__(self, room_id: str, hostel_type: str):
        self.room_id = room_id
        self.hostel_type = hostel_type
        self.connections: dict[WebSocket, dict] = {}
    
    @property
    def is_full(self) -> bool:
        return len(self.connections) >= 15

class ConnectionManager:
    def __init__(self):
        self.rooms: dict[str, Room] = {}
        self.ws_to_room: dict[WebSocket, str] = {}
        
        self.active_users: dict[str, WebSocket] = {}

    def get_room_stats(self, hostel_type: str) -> list[dict]:
        stats = []
        for room in self.rooms.values():
            if room.hostel_type == hostel_type:
                stats.append({
                    "room_id": room.room_id,
                    "user_count": len(room.connections),
                    "is_full": room.is_full
                })
        return sorted(stats, key=lambda x: int(x["room_id"].split('-')[1]))

    async def broadcast_stats(self, hostel_type: str):
        stats = self.get_room_stats(hostel_type)
        message = {"type": "room_stats", "rooms": stats}
        
        for room in self.rooms.values():
            if room.hostel_type == hostel_type:
                for connection in room.connections.keys():
                    await connection.send_json(message)

    async def connect(self, websocket: WebSocket, user_info: dict, hostel_type: str) -> str:
        await websocket.accept()
        
        self.active_users[user_info["regNo"]] = websocket
        
        available_room = None
        for room in self.rooms.values():
            if room.hostel_type == hostel_type and not room.is_full:
                available_room = room
                break
        
        if not available_room:
            room_num = 1
            while f"{hostel_type}-{room_num}" in self.rooms:
                room_num += 1
                
            room_id = f"{hostel_type}-{room_num}"
            available_room = Room(room_id, hostel_type)
            self.rooms[room_id] = available_room
        
        available_room.connections[websocket] = user_info
        self.ws_to_room[websocket] = available_room.room_id
        return available_room.room_id

    def disconnect(self, websocket: WebSocket) -> tuple[str | None, str | None]:
        room_id = self.ws_to_room.get(websocket)
        hostel_type = None
        
        if room_id and room_id in self.rooms:
            room = self.rooms[room_id]
            hostel_type = room.hostel_type
            
            user_info = room.connections.get(websocket)
            if user_info and user_info["regNo"] in self.active_users:
                del self.active_users[user_info["regNo"]]
                
            if websocket in room.connections:
                del room.connections[websocket]
            del self.ws_to_room[websocket]
            
            if len(room.connections) == 0:
                del self.rooms[room_id]
                
        return room_id, hostel_type

    async def switch_room(self, websocket: WebSocket, target_room_id: str, user_info: dict, hostel_type: str) -> bool:
        target_room = self.rooms.get(target_room_id)
        
        if not target_room or target_room.hostel_type != hostel_type:
            await websocket.send_json({"type": "error", "message": "Room does not exist."})
            return False
        if target_room.is_full:
            await websocket.send_json({"type": "error", "message": f"{target_room_id} is currently full (15/15)."})
            return False

        old_room_id = self.ws_to_room.get(websocket)
        if old_room_id and old_room_id in self.rooms:
            del self.rooms[old_room_id].connections[websocket]
            
            await self.broadcast_to_room(old_room_id, {
                "type": "system",
                "message": f"🚪 {user_info['name']} moved to another room.",
                "room_id": old_room_id,
                "user_count": len(self.rooms[old_room_id].connections),
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
            
            if len(self.rooms[old_room_id].connections) == 0:
                del self.rooms[old_room_id]

        target_room.connections[websocket] = user_info
        self.ws_to_room[websocket] = target_room_id
        return True

    async def broadcast_to_room(self, room_id: str, message_data: dict):
        if room_id in self.rooms:
            room = self.rooms[room_id]
            if message_data.get("type") == "system":
                message_data["room_id"] = room_id
                message_data["user_count"] = len(room.connections)
            
            for connection in room.connections.keys():
                await connection.send_json(message_data)

manager = ConnectionManager()

@router.websocket("/ws/{reg_no}")
async def websocket_endpoint(
    websocket: WebSocket, 
    reg_no: str, 
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    
    if reg_no in manager.active_users:
        await websocket.accept()
        await websocket.send_json({
            "type": "error", 
            "message": "You are already connected in another tab or device. Please close it before joining here."
        })
        await websocket.close(code=1008)
        return

    student_service = StudentService(db)
    student = await student_service.get_by_reg_no(reg_no)

    if not student or not student.get("hostelType"):
        await websocket.close(code=1008) 
        return

    hostel_type = student.get("hostelType")
    user_info = {
        "regNo": student.get("regNo"),
        "name": student.get("name")
    }

    room_id = await manager.connect(websocket, user_info, hostel_type)
    
    await manager.broadcast_to_room(room_id, {
        "type": "system",
        "message": f"👋 {user_info['name']} joined.",
        "timestamp": datetime.now(timezone.utc).isoformat()
    })
    
    await manager.broadcast_stats(hostel_type)
    
    try:
        while True:
            raw_data = await websocket.receive_text()
            try:
                data = json.loads(raw_data)
            except json.JSONDecodeError:
                continue

            action = data.get("action")
            current_room = manager.ws_to_room.get(websocket)

            if action == "chat" and current_room:
                await manager.broadcast_to_room(current_room, {
                    "type": "chat",
                    "sender_name": user_info["name"],
                    "sender_reg_no": user_info["regNo"],
                    "room_id": current_room,
                    "message": data.get("message"),
                    "timestamp": datetime.now(timezone.utc).isoformat()
                })
                
            elif action == "switch_room":
                target_room = data.get("target_room")
                if target_room == current_room:
                    continue
                
                success = await manager.switch_room(websocket, target_room, user_info, hostel_type)
                if success:
                    await manager.broadcast_to_room(target_room, {
                        "type": "system",
                        "message": f"👋 {user_info['name']} joined the room.",
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    })
                    await manager.broadcast_stats(hostel_type)
            
    except WebSocketDisconnect:
        disconnected_room_id, d_hostel_type = manager.disconnect(websocket)
        if disconnected_room_id:
            await manager.broadcast_to_room(disconnected_room_id, {
                "type": "system",
                "message": f"🚪 {user_info['name']} disconnected.",
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
        if d_hostel_type:
            await manager.broadcast_stats(d_hostel_type)