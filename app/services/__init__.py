"""User Service"""
from typing import Optional
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson import ObjectId
from app.models import User
from app.schemas import UserLogin


class UserService:
    """User service for database operations"""
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.collection = db["users"]

    @staticmethod
    def _to_user(user_doc: dict | None) -> Optional[User]:
        """Normalize Mongo document into User model."""
        if not user_doc:
            return None

        normalized = dict(user_doc)
        mongo_id = normalized.pop("_id", None)
        if mongo_id is not None:
            normalized["id"] = str(mongo_id)

        return User(**normalized)
    
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
        return self._to_user(user_doc)
    
    async def get_user_by_google_id(self, google_id: str) -> Optional[User]:
        """Get user by Google ID"""
        user_doc = await self.collection.find_one({"google_id": google_id})
        return self._to_user(user_doc)
    
    async def get_user_by_id(self, user_id: str) -> Optional[User]:
        """Get user by ID"""
        try:
            user_doc = await self.collection.find_one({"_id": ObjectId(user_id)})
            return self._to_user(user_doc)
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
            return self._to_user(result)
        except:
            pass
        return None


from app.services.group_request_service import GroupRequestService
from app.services.group_service import GroupService
from app.services.student_service import StudentService
