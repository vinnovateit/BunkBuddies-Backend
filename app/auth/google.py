"""Google OAuth Handler (Authlib)"""
from authlib.integrations.httpx_client import AsyncOAuth2Client

from config import settings

GOOGLE_AUTH_URI = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URI = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URI = "https://www.googleapis.com/oauth2/v2/userinfo"
GOOGLE_SCOPES = "openid email profile"


async def get_authorization_url() -> tuple[str, str]:
    client = AsyncOAuth2Client(
        client_id=settings.google_client_id,
        client_secret=settings.google_client_secret,
        redirect_uri=settings.google_redirect_uri,
        scope=GOOGLE_SCOPES,
    )
    authorization_url, state = client.create_authorization_url(
        GOOGLE_AUTH_URI,
        access_type="offline",
        include_granted_scopes="true",
        hd="vitstudent.ac.in"
    )
    await client.aclose()
    return authorization_url, state


async def fetch_google_user_info(code: str) -> dict:
    client = AsyncOAuth2Client(
        client_id=settings.google_client_id,
        client_secret=settings.google_client_secret,
        redirect_uri=settings.google_redirect_uri,
        scope=GOOGLE_SCOPES,
    )
    try:
        token = await client.fetch_token(
            GOOGLE_TOKEN_URI,
            code=code,
            grant_type="authorization_code",
        )
        access_token = token.get("access_token")
        if not access_token:
            raise ValueError("Google token response missing access_token")

        response = await client.get(
            GOOGLE_USERINFO_URI,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        response.raise_for_status()
        return response.json()
    finally:
        await client.aclose()
