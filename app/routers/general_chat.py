import json
from datetime import datetime, timezone
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.database import get_database
from app.services.student_service import StudentService
from app.models.bunk import GeneralMessage 

router = APIRouter(prefix="/generalChat", tags=["generalChat"])

class Room:
    def __init__(self, room_id: str):
        self.room_id = room_id
        self.connections: dict[WebSocket, dict] = {}

class ConnectionManager:
    def __init__(self):
        self.rooms: dict[str, Room] = {}
        self.ws_to_room: dict[WebSocket, str] = {}
        self.active_users: dict[str, WebSocket] = {}

    def get_all_room_stats(self) -> list[dict]:
        """Returns the user count for all active rooms."""
        stats = []
        for room_id, room in self.rooms.items():
            stats.append({
                "room_id": room_id,
                "user_count": len(room.connections)
            })
        return stats

    async def broadcast_stats(self):
        """Broadcasts global room stats to EVERY connected user."""
        stats = self.get_all_room_stats()
        message = {"type": "room_stats", "rooms": stats} 
        
        for room in self.rooms.values():
            for connection in room.connections.keys():
                try:
                    await connection.send_json(message)
                except Exception:
                    pass # Ignore if connection is dropping

    async def connect(self, websocket: WebSocket, user_info: dict, hostel_type: str) -> str:
        await websocket.accept()
        
        self.active_users[user_info["regNo"]] = websocket
        
        # Room ID is simply the hostel type itself (e.g., "MH" or "LH")
        room_id = hostel_type 
        
        if room_id not in self.rooms:
            self.rooms[room_id] = Room(room_id)
        
        self.rooms[room_id].connections[websocket] = user_info
        self.ws_to_room[websocket] = room_id
        return room_id

    def disconnect(self, websocket: WebSocket) -> str | None:
        room_id = self.ws_to_room.get(websocket)
        
        if room_id and room_id in self.rooms:
            room = self.rooms[room_id]
            
            user_info = room.connections.get(websocket)
            if user_info and user_info["regNo"] in self.active_users:
                del self.active_users[user_info["regNo"]]
                
            if websocket in room.connections:
                del room.connections[websocket]
            del self.ws_to_room[websocket]
            
            if len(room.connections) == 0:
                del self.rooms[room_id]
                
        return room_id

    async def broadcast_to_room(self, room_id: str, message_data: dict):
        if room_id in self.rooms:
            # Create a list of connections to avoid dict size changing during iteration
            connections = list(self.rooms[room_id].connections.keys())
            for connection in connections:
                try:
                    await connection.send_json(message_data)
                except RuntimeError:
                    # Connection dropped unexpectedly, disconnect them safely
                    self.disconnect(connection)

manager = ConnectionManager()

@router.get("/history/{room_id}")
async def get_room_history(
    room_id: str, 
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Fetch the full chat history for a specific room."""
    cursor = db["general_messages"].find({"room_id": room_id}).sort("timestamp", 1)
    
    messages = await cursor.to_list(length=None) 
    
    for msg in messages:
        msg["id"] = str(msg["_id"])
        del msg["_id"]
        # Ensure UTC timezone is attached before sending to frontend
        if "timestamp" in msg and msg["timestamp"].tzinfo is None:
            msg["timestamp"] = msg["timestamp"].replace(tzinfo=timezone.utc)
        
    return messages

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
    
    await websocket.send_json({"type": "welcome", "room_id": room_id})
    # Update active room counts for everyone
    await manager.broadcast_stats()
    
    try:
        while True:
            raw_data = await websocket.receive_text()
            try:
                data = json.loads(raw_data)
            except json.JSONDecodeError:
                continue

            action = data.get("action")
            text_content = data.get("message", "").strip()
            current_room = manager.ws_to_room.get(websocket)

            # Ignore empty messages
            if action == "chat" and current_room and text_content:
                
                # 1. Validate data using Pydantic Schema
                new_message = GeneralMessage(
                    room_id=current_room,
                    sender_name=user_info["name"],
                    sender_reg_no=user_info["regNo"],
                    message=text_content
                )
                
                # Convert to dict for MongoDB (exclude 'id' so Mongo creates '_id')
                db_message = new_message.model_dump(exclude={"id"})
                result = await db["general_messages"].insert_one(db_message)

                # 2. Broadcast to room
                broadcast_payload = {
                    "id": str(result.inserted_id),
                    "type": "chat",
                    "sender_name": new_message.sender_name,
                    "sender_reg_no": new_message.sender_reg_no,
                    "room_id": new_message.room_id,
                    "message": new_message.message,
                    "timestamp": new_message.timestamp.isoformat()
                }
                await manager.broadcast_to_room(current_room, broadcast_payload)
                
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        await manager.broadcast_stats()