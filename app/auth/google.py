"""Google OAuth Handler"""
import os
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from config import settings


def get_google_flow():
    """Initialize Google OAuth flow"""
    flow = Flow.from_client_secrets_file(
        'credentials.json',
        scopes=[
            'https://www.googleapis.com/auth/userinfo.profile',
            'https://www.googleapis.com/auth/userinfo.email'
        ],
        redirect_uri=settings.google_redirect_uri
    )
    return flow


def get_authorization_url():
    """Get Google authorization URL"""
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
    
    authorization_url, state = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true'
    )
    
    return authorization_url, state, flow


def get_user_info_from_token(token):
    """Get user information from Google token"""
    import httpx
    
    headers = {'Authorization': f'Bearer {token}'}
    response = httpx.get(
        'https://www.googleapis.com/oauth2/v2/userinfo',
        headers=headers
    )
    
    if response.status_code == 200:
        return response.json()
    return None
