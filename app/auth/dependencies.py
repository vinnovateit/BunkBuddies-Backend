from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.auth.jwt import decode_access_token
from app.database import get_database
from app.schemas import CurrentAuthUser
from app.services import UserService

bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_auth_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> CurrentAuthUser:
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="You are not authorized to access this resource. Please login and try again.",
        )

    payload = decode_access_token(credentials.credentials)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="You are not authorized to access this resource. Please login and try again.",
        )

    user_id = payload.get("sub")
    email = payload.get("email")
    if not user_id or not email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="You are not authorized to access this resource. Please login and try again.",
        )

    db = get_database()
    user_service = UserService(db)
    user = await user_service.get_user_by_id(user_id)

    if not user or not user.google_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="You are not authorized to access this resource. Please login and try again.",
        )

    return CurrentAuthUser(user_id=user_id, uid=user.google_id, email=user.email)
