"""Read-only YouTube OAuth and Analytics API integration.

OAuth refresh credentials are stored in AWS Secrets Manager. Google client
credentials are supplied through environment variables and must never be
committed to the repository.
"""
import json
import logging
import secrets
import time
from urllib.parse import urlencode

import boto3
import httpx
from fastapi import HTTPException
from .config import settings

logger = logging.getLogger(__name__)
GOOGLE_AUTH = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN = "https://oauth2.googleapis.com/token"
ANALYTICS_API = "https://youtubeanalytics.googleapis.com/v2/reports"
YOUTUBE_API = "https://www.googleapis.com/youtube/v3"
SCOPES = [
    "https://www.googleapis.com/auth/youtube.readonly",
    "https://www.googleapis.com/auth/yt-analytics.readonly",
]
_pending_states: dict[str, float] = {}


def oauth_ready() -> bool:
    return bool(settings.google_client_id and settings.google_client_secret and
                settings.youtube_oauth_redirect_uri and settings.youtube_token_secret_id)


def create_authorization_url() -> str:
    if not oauth_ready():
        raise HTTPException(status_code=503, detail="YouTube OAuth configuration is incomplete")
    state = secrets.token_urlsafe(32)
    now = time.time()
    _pending_states.clear()
    _pending_states[state] = now
    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": settings.youtube_oauth_redirect_uri,
        "response_type": "code",
        "scope": " ".join(SCOPES),
        "access_type": "offline",
        "prompt": "consent",
        "include_granted_scopes": "true",
        "state": state,
    }
    return f"{GOOGLE_AUTH}?{urlencode(params)}"


def _secret_client():
    return boto3.client("secretsmanager", region_name=settings.aws_region)


def save_refresh_token(token_payload: dict) -> None:
    refresh_token = token_payload.get("refresh_token")
    if not refresh_token:
        # Google may omit a refresh token on subsequent consent grants.
        existing = load_token_secret()
        refresh_token = existing.get("refresh_token")
    if not refresh_token:
        raise RuntimeError("Google did not return a refresh token; revoke app access and authorize again")
    payload = {
        "refresh_token": refresh_token,
        "scope": token_payload.get("scope", ""),
        "token_type": token_payload.get("token_type", "Bearer"),
        "updated_at": int(time.time()),
    }
    _secret_client().put_secret_value(
        SecretId=settings.youtube_token_secret_id,
        SecretString=json.dumps(payload),
    )


def load_token_secret() -> dict:
    try:
        result = _secret_client().get_secret_value(SecretId=settings.youtube_token_secret_id)
        return json.loads(result["SecretString"])
    except Exception as exc:
        logger.warning("Could not read YouTube token secret (%s)", type(exc).__name__)
        raise


async def exchange_authorization_code(code: str) -> dict:
    data = {
        "code": code,
        "client_id": settings.google_client_id,
        "client_secret": settings.google_client_secret,
        "redirect_uri": settings.youtube_oauth_redirect_uri,
        "grant_type": "authorization_code",
    }
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(GOOGLE_TOKEN, data=data)
        response.raise_for_status()
        payload = response.json()
    save_refresh_token(payload)
    return payload


async def access_token() -> str:
    stored = load_token_secret()
    refresh_token = stored.get("refresh_token")
    if not refresh_token:
        raise HTTPException(status_code=503, detail="YouTube channel is not connected")
    data = {
        "client_id": settings.google_client_id,
        "client_secret": settings.google_client_secret,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
    }
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(GOOGLE_TOKEN, data=data)
        response.raise_for_status()
        payload = response.json()
    return payload["access_token"]


async def analytics_report(start_date: str, end_date: str, dimensions: str | None = None,
                           metrics: str = "views,estimatedMinutesWatched,subscribersGained,subscribersLost,likes,comments",
                           sort: str | None = None, max_results: int = 10) -> dict:
    token = await access_token()
    params = {
        "ids": "channel==MINE",
        "startDate": start_date,
        "endDate": end_date,
        "metrics": metrics,
        "maxResults": max_results,
    }
    if dimensions:
        params["dimensions"] = dimensions
    if sort:
        params["sort"] = sort
    async with httpx.AsyncClient(timeout=45) as client:
        response = await client.get(
            ANALYTICS_API, params=params,
            headers={"Authorization": f"Bearer {token}"},
        )
        response.raise_for_status()
        return response.json()


async def channel_info() -> dict:
    token = await access_token()
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(
            f"{YOUTUBE_API}/channels",
            params={"part": "snippet,statistics", "mine": "true"},
            headers={"Authorization": f"Bearer {token}"},
        )
        response.raise_for_status()
        data = response.json()
    items = data.get("items", [])
    return items[0] if items else {}
