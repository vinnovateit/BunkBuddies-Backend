"""Authentication Routes"""
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
import httpx

from config import settings
from app.database import get_database
from app.services import UserService
from app.schemas import UserLogin, TokenResponse, UserResponse
from app.auth.jwt import create_access_token
from app.auth.google import get_authorization_url, get_user_info_from_token

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/login")
async def google_login():
    """Initiate Google OAuth login"""
    authorization_url, state, _ = get_authorization_url()
    # In production, store state in session/cache for security
    return {"authorization_url": authorization_url, "state": state}


@router.get("/callback")
async def google_callback(
    code: str = Query(...),
    state: str = Query(...)
):
    """Google OAuth callback"""
    try:
        # Exchange code for token
        from google_auth_oauthlib.flow import Flow
        
        flow = Flow.from_client_config(
            {
                "installed": {
                    "client_id": settings.google_client_id,
                    "client_secret": settings.google_client_secret,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "redirect_uris": [settings.google_redirect_uri]
                }
            },
            scopes=[
                'https://www.googleapis.com/auth/userinfo.profile',
                'https://www.googleapis.com/auth/userinfo.email'
            ],
            redirect_uri=settings.google_redirect_uri
        )
        
        flow.fetch_token(authorization_response=f"{settings.google_redirect_uri}?code={code}&state={state}")
        credentials = flow.credentials
        
        # Get user info
        async with httpx.AsyncClient() as client:
            response = await client.get(
                'https://www.googleapis.com/oauth2/v2/userinfo',
                headers={'Authorization': f'Bearer {credentials.token}'}
            )
        
        if response.status_code != 200:
            raise HTTPException(status_code=400, detail="Failed to get user info from Google")
        
        user_info = response.json()
        
        # Get or create user
        db = get_database()
        user_service = UserService(db)
        
        existing_user = await user_service.get_user_by_google_id(user_info.get("id"))
        
        if existing_user:
            user = existing_user
        else:
            user_data = UserLogin(
                email=user_info.get("email"),
                first_name=user_info.get("given_name", ""),
                last_name=user_info.get("family_name", ""),
                picture=user_info.get("picture"),
                google_id=user_info.get("id")
            )
            user = await user_service.create_user(user_data)
        
        # Create JWT token
        access_token = create_access_token(
            data={"sub": user.id, "email": user.email}
        )
        
        # Return token (in production, redirect to frontend with token in URL/cookie)
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "user": UserResponse(**user.model_dump())
        }
    
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
