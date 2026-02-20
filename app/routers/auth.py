"""Authentication Routes"""
import re

from fastapi import APIRouter, Depends, HTTPException, Query

from app.auth.dependencies import get_current_auth_user
from app.database import get_database
from app.services import UserService
from app.schemas import CurrentAuthUser, SignupStudentRequest, UserLogin, UserResponse
from app.auth.jwt import create_access_token
from app.auth.google import fetch_google_user_info, get_authorization_url

router = APIRouter(prefix="/auth", tags=["auth"])


def _extract_reg_no_from_email(email: str) -> str | None:
    local_part = email.split("@")[0].upper().replace(".", "")
    if re.match(r"^\d{2}[A-Z]{3}\d{4}$", local_part):
        return local_part
    return None


def _extract_name(user_info: dict) -> str:
    full_name = (user_info.get("name") or "").strip()
    if full_name:
        return full_name

    first_name = (user_info.get("given_name") or "").strip()
    last_name = (user_info.get("family_name") or "").strip()
    fallback = f"{first_name} {last_name}".strip()
    if fallback:
        return fallback

    email = (user_info.get("email") or "").strip()
    return email.split("@")[0] if email else ""




@router.get("/meDetails")
async def get_signed_in_details(
    current_user: CurrentAuthUser = Depends(get_current_auth_user),
):
    db = get_database()
    user_service = UserService(db)
    student_collection = db["students"]

    user = await user_service.get_user_by_id(current_user.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    student = await student_collection.find_one({"firebaseUID": user.google_id})

    reg_no = _extract_reg_no_from_email(user.email)
    name = f"{user.first_name} {user.last_name}".strip()

    return {
        "message": "User details fetched",
        "details": {
            "email": user.email,
            "name": student.get("name") if student else name,
            "regNo": student.get("regNo") if student else reg_no,
            "firebaseUID": user.google_id,
            "photoURL": student.get("photoURL") if student else user.picture,
        },
    }


@router.get("/login")
async def google_login():
    """Initiate Google OAuth login"""
    authorization_url, state = await get_authorization_url()
    # In production, store state in session/cache for security
    return {"authorization_url": authorization_url, "state": state}


@router.get("/callback")
async def google_callback(
    code: str = Query(...),
    state: str = Query(...)
):
    """Google OAuth callback"""
    try:
        user_info = await fetch_google_user_info(code)
        email = (user_info.get("email") or "").strip()
        name = _extract_name(user_info)
        reg_no = _extract_reg_no_from_email(email)
        
        # Get or create user
        db = get_database()
        user_service = UserService(db)
        
        existing_user = await user_service.get_user_by_google_id(user_info.get("id"))
        
        if existing_user:
            user = existing_user
        else:
            user_data = UserLogin(
                email=email,
                first_name=user_info.get("given_name", ""),
                last_name=user_info.get("family_name", ""),
                picture=user_info.get("picture"),
                google_id=user_info.get("id")
            )
            user = await user_service.create_user(user_data)

        student_collection = db["students"]
        existing_student = await student_collection.find_one({"firebaseUID": user_info.get("id")})

        student_payload = {
            "name": name,
            "email": email,
            "firebaseUID": user_info.get("id"),
            "photoURL": user_info.get("picture"),
        }

        if reg_no:
            student_payload["regNo"] = reg_no

        if existing_student:
            await student_collection.update_one(
                {"firebaseUID": user_info.get("id")},
                {"$set": student_payload},
            )
        elif reg_no:
            # Create student profile automatically only when regNo can be inferred from email
            # and no profile exists yet for this UID.
            duplicate_reg = await student_collection.find_one({"regNo": reg_no})
            if not duplicate_reg:
                await student_collection.insert_one(student_payload)
        
        # Create JWT token
        access_token = create_access_token(
            data={"sub": user.id, "email": user.email}
        )
        
        # Return token (in production, redirect to frontend with token in URL/cookie)
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "user": UserResponse(**user.model_dump()),
            "details": {
                "email": email,
                "name": name,
                "regNo": reg_no,
                "firebaseUID": user_info.get("id"),
                "photoURL": user_info.get("picture"),
            },
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Authentication failed: {str(e)}")


@router.get("/me", response_model=UserResponse)
async def get_current_user(
    authorization: str = Depends(lambda: None)
):
    """Get current user info from token"""
    from fastapi.security import HTTPBearer, HTTPAuthenticationCredentials
    from fastapi import Header
    
    # This is a simplified version. Implement proper Bearer token extraction
    raise HTTPException(status_code=401, detail="Not authenticated")
