"""User Service"""
from typing import Optional
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson import ObjectId
from app.models import User
from app.schemas import UserLogin, UserResponse


class UserService:
    """User service for database operations"""
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.collection = db["users"]
    
    async def create_user(self, user_data: UserLogin) -> User:
        """Create a new user"""
        user = User(
            email=user_data.email,
            first_name=user_data.first_name,
            last_name=user_data.last_name,
            picture=user_data.picture,
            google_id=user_data.google_id
        )
        
        result = await self.collection.insert_one(user.model_dump(exclude={"id"}))
        user.id = str(result.inserted_id)
        
        return user
    
    async def get_user_by_email(self, email: str) -> Optional[User]:
        """Get user by email"""
        user_doc = await self.collection.find_one({"email": email})
        if user_doc:
            user_doc["id"] = str(user_doc["_id"])
            return User(**user_doc)
        return None
    
    async def get_user_by_google_id(self, google_id: str) -> Optional[User]:
        """Get user by Google ID"""
        user_doc = await self.collection.find_one({"google_id": google_id})
        if user_doc:
            user_doc["id"] = str(user_doc["_id"])
            return User(**user_doc)
        return None
    
    async def get_user_by_id(self, user_id: str) -> Optional[User]:
        """Get user by ID"""
        try:
            user_doc = await self.collection.find_one({"_id": ObjectId(user_id)})
            if user_doc:
                user_doc["id"] = str(user_doc["_id"])
                return User(**user_doc)
        except:
            pass
        return None
    
    async def update_user(self, user_id: str, update_data: dict) -> Optional[User]:
        """Update user"""
        try:
            update_data["updated_at"] = datetime.utcnow()
            result = await self.collection.find_one_and_update(
                {"_id": ObjectId(user_id)},
                {"$set": update_data},
                return_document=True
            )
            if result:
                result["id"] = str(result["_id"])
                return User(**result)
        except:
            pass
        return None
