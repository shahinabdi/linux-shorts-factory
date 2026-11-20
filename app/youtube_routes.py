from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
import logging
import secrets
import time

from .config import settings
from .youtube import (
    create_authorization_url, exchange_authorization_code,
    _pending_states, oauth_ready, channel_info
)

router = APIRouter()
logger = logging.getLogger(__name__)
basic_auth = HTTPBasic()


def require_admin(credentials: HTTPBasicCredentials = Depends(basic_auth)):
    expected = settings.factory_admin_key
    if not expected or not secrets.compare_digest(credentials.password, expected):
        raise HTTPException(
            status_code=401,
            detail="Invalid admin credentials",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username


@router.get("/youtube/oauth/start")
def oauth_start(_admin: str = Depends(require_admin)):
    return RedirectResponse(create_authorization_url(), status_code=302)


@router.get("/youtube/oauth/callback", response_class=HTMLResponse)
async def oauth_callback(code: str | None = None, state: str | None = None,
                         error: str | None = None):
    if error:
        return HTMLResponse("<h2>YouTube authorization was not completed.</h2>", status_code=400)
    valid = bool(state and state in _pending_states and time.time() - _pending_states[state] < 600)
    _pending_states.clear()
    if not valid or not code:
        raise HTTPException(status_code=400, detail="Invalid or expired OAuth state")
    try:
        await exchange_authorization_code(code)
        info = await channel_info()
        title = (info.get("snippet") or {}).get("title", "YouTube channel")
        return HTMLResponse(
            "<h2>YouTube channel connected successfully.</h2>"
            f"<p>Connected channel: {title}</p><p>You may close this window.</p>"
        )
    except Exception as exc:
        logger.exception("YouTube OAuth callback failed")
        return HTMLResponse(
            f"<h2>Connection failed: {type(exc).__name__}</h2><p>Check server logs.</p>",
            status_code=502,
        )


@router.get("/youtube/status")
async def youtube_status():
    if not oauth_ready():
        return {"configured": False, "connected": False}
    try:
        info = await channel_info()
        return {
            "configured": True,
            "connected": True,
            "channel_title": (info.get("snippet") or {}).get("title"),
            "channel_id": info.get("id"),
        }
    except Exception:
        return {"configured": True, "connected": False}
