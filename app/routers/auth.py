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


_REG_NO_CANDIDATE_PATTERN = re.compile(r"\b([0-9Oo]{2}[A-Za-z]{3}[0-9Oo]{4})\b")
_REG_NO_NUMERIC_INDEXES = (0, 1, 5, 6, 7, 8)
_REG_NO_ALPHA_INDEXES = (2, 3, 4)


def _normalize_reg_no_candidate(raw: str) -> str | None:
    cleaned = re.sub(r"[^A-Za-z0-9]", "", raw or "").upper()
    if len(cleaned) != 9:
        return None

    chars = list(cleaned)
    for index in _REG_NO_NUMERIC_INDEXES:
        if chars[index] == "O":
            chars[index] = "0"
        if not chars[index].isdigit():
            return None

    for index in _REG_NO_ALPHA_INDEXES:
        if not chars[index].isalpha():
            return None

    return "".join(chars)


def _extract_reg_no_from_text(value: str | None) -> str | None:
    if not value:
        return None

    match = _REG_NO_CANDIDATE_PATTERN.search(value)
    if not match:
        return None

    return _normalize_reg_no_candidate(match.group(1))


def _extract_reg_no_from_email(email: str) -> str | None:
    local_part = email.split("@")[0]
    return _extract_reg_no_from_text(local_part)


def _fallback_reg_no(email: str, google_id: str | None) -> str:
    if google_id:
        return f"UID{google_id}"
    return "UNKNOWN"


def _strip_reg_no_from_name(value: str, reg_no: str | None) -> str:
    cleaned = re.sub(r"\s+", " ", (value or "").strip())
    if not cleaned:
        return ""

    if reg_no:
        cleaned = re.sub(re.escape(reg_no), "", cleaned, flags=re.IGNORECASE).strip()

    cleaned = _REG_NO_CANDIDATE_PATTERN.sub("", cleaned).strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned


def _extract_name(user_info: dict, reg_no: str | None) -> str:
    full_name = (user_info.get("name") or "").strip()
    if full_name:
        stripped = _strip_reg_no_from_name(full_name, reg_no)
        if stripped:
            return stripped

    first_name = (user_info.get("given_name") or "").strip()
    last_name = (user_info.get("family_name") or "").strip()
    fallback = f"{first_name} {last_name}".strip()
    if fallback:
        stripped = _strip_reg_no_from_name(fallback, reg_no)
        if stripped:
            return stripped

    email = (user_info.get("email") or "").strip()
    local_part = email.split("@")[0] if email else ""
    return local_part.replace(".", " ").strip()


def _validate_redirect_uri(redirect_uri: str | None) -> str | None:
    if redirect_uri and not redirect_uri.startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail="Invalid redirect_uri")
    return redirect_uri


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
async def google_login(
    redirect_uri: str | None = Query(default=None),
):
    """Initiate Google OAuth login"""
    redirect_uri = _validate_redirect_uri(redirect_uri)
    authorization_url, state = await get_authorization_url(redirect_uri=redirect_uri)
    # In production, store state in session/cache for security
    return {"authorization_url": authorization_url, "state": state}


@router.get("/callback")
async def google_callback(
    code: str = Query(...),
    state: str = Query(...),
    redirect_uri: str | None = Query(default=None),
):
    """Google OAuth callback"""
    try:
        redirect_uri = _validate_redirect_uri(redirect_uri)
        user_info = await fetch_google_user_info(code, redirect_uri=redirect_uri)
        email = (user_info.get("email") or "").strip()
        reg_no = (
            _extract_reg_no_from_email(email)
            or _extract_reg_no_from_text(user_info.get("name"))
            or _extract_reg_no_from_text(
                f"{(user_info.get('given_name') or '').strip()} {(user_info.get('family_name') or '').strip()}".strip()
            )
        )
        name = _extract_name(user_info, reg_no)

        # Restrict to @vitstudent.ac.in emails only
        if not email.lower().endswith("@vitstudent.ac.in"):
            raise HTTPException(status_code=403, detail="Only @vitstudent.ac.in email addresses are allowed.")

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

        resolved_reg_no = reg_no or _fallback_reg_no(email, user_info.get("id"))
        student_payload["regNo"] = resolved_reg_no

        if existing_student:
            await student_collection.update_one(
                {"firebaseUID": user_info.get("id")},
                {"$set": student_payload},
            )
        else:
            # Ensure there is always a student profile for logged-in users.
            duplicate_reg = await student_collection.find_one({"regNo": resolved_reg_no})
            if duplicate_reg:
                await student_collection.update_one(
                    {"_id": duplicate_reg["_id"]},
                    {"$set": student_payload},
                )
            else:
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
                "regNo": resolved_reg_no,
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
