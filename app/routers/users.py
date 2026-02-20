"""Users Routes"""
from fastapi import APIRouter, Depends, HTTPException
from app.database import get_database
from app.services import UserService
from app.schemas import UserResponse

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/{userId}", response_model=UserResponse)
async def get_user(user_id: str):
    """Get user by ID"""
    db = get_database()
    user_service = UserService(db)
    
    user = await user_service.get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return UserResponse(**user.model_dump())
