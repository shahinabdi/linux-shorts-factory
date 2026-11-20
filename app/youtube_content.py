"""Read-only helpers for richer YouTube content reports.

Shorts classification is based on YouTube Analytics creatorContentType, not
video duration, because duration alone cannot distinguish a Short reliably.
"""
from datetime import date, timedelta
import httpx

from .youtube import access_token, channel_info, YOUTUBE_API, ANALYTICS_API


async def _youtube_get(path: str, params: dict) -> dict:
    token = await access_token()
    async with httpx.AsyncClient(timeout=40) as client:
        response = await client.get(
            f"{YOUTUBE_API}/{path}", params=params,
            headers={"Authorization": f"Bearer {token}"},
        )
        response.raise_for_status()
        return response.json()


async def _analytics_video_rows(start: date, end: date, content_type: str | None = None,
                                max_results: int = 5) -> list[dict]:
    """Fetch per-video rows and classify locally using creatorContentType dimension."""
    token = await access_token()
    params = {
        "ids": "channel==MINE",
        "startDate": start.isoformat(),
        "endDate": end.isoformat(),
        "dimensions": "video,creatorContentType",
        "metrics": "views,estimatedMinutesWatched,averageViewDuration,averageViewPercentage,likes,comments,subscribersGained",
        "sort": "-views",
        "maxResults": 200,
    }
    async with httpx.AsyncClient(timeout=45) as client:
        response = await client.get(
            ANALYTICS_API, params=params,
            headers={"Authorization": f"Bearer {token}"},
        )
        response.raise_for_status()
        data = response.json()
    headers = [h.get("name") for h in data.get("columnHeaders", [])]
    rows = [dict(zip(headers, row)) for row in data.get("rows", []) or []]
    if content_type:
        rows = [row for row in rows if row.get("creatorContentType") == content_type]
    return rows[:max_results]


async def _video_metadata(video_ids: list[str]) -> dict[str, dict]:
    result = {}
    for offset in range(0, len(video_ids), 50):
        batch = video_ids[offset:offset + 50]
        if not batch:
            continue
        data = await _youtube_get("videos", {
            "part": "snippet,contentDetails,statistics",
            "id": ",".join(batch),
            "maxResults": 50,
        })
        for item in data.get("items", []):
            result[item["id"]] = item
    return result


async def top_videos(start: date, end: date, content_type: str | None = "VIDEO_ON_DEMAND",
                     limit: int = 5) -> list[dict]:
    rows = await _analytics_video_rows(start, end, content_type, limit)
    metadata = await _video_metadata([r["video"] for r in rows if r.get("video")])
    output = []
    for row in rows:
        video_id = row.get("video")
        item = metadata.get(video_id, {})
        snippet = item.get("snippet", {})
        output.append({
            "id": video_id,
            "title": snippet.get("title", video_id or "Unknown video"),
            "published_at": snippet.get("publishedAt", ""),
            "url": f"https://www.youtube.com/watch?v={video_id}" if video_id else "",
            **row,
        })
    return output


async def recent_uploads(limit: int = 30) -> list[dict]:
    info = await channel_info()
    uploads = (((info.get("contentDetails") or {}).get("relatedPlaylists") or {}).get("uploads"))
    if not uploads:
        return []
    data = await _youtube_get("playlistItems", {
        "part": "snippet,contentDetails",
        "playlistId": uploads,
        "maxResults": min(max(limit, 1), 50),
    })
    ids = []
    for entry in data.get("items", []):
        video_id = (entry.get("contentDetails") or {}).get("videoId")
        if video_id:
            ids.append(video_id)
    metadata = await _video_metadata(ids)
    return [metadata[video_id] for video_id in ids if video_id in metadata]


async def recent_shorts(limit: int = 5) -> list[dict]:
    # Inspect recent uploads and verify each candidate against Analytics'
    # creatorContentType filter; duration is deliberately not used as proof.
    uploads = await recent_uploads(20)
    selected = []
    end = date.today() - timedelta(days=2)
    for item in uploads:
        video_id = item.get("id")
        if not video_id:
            continue
        published = (item.get("snippet") or {}).get("publishedAt", "")[:10]
        start = date.fromisoformat(published) if published else end - timedelta(days=89)
        if start > end:
            continue
        rows = await _analytics_video_rows_for_id(start, end, video_id, "SHORTS")
        if rows:
            row = rows[0]
            snippet = item.get("snippet", {})
            selected.append({
                "id": video_id,
                "title": snippet.get("title", video_id),
                "published_at": snippet.get("publishedAt", ""),
                "url": f"https://www.youtube.com/shorts/{video_id}",
                "views": row.get("views", 0),
                "averageViewPercentage": row.get("averageViewPercentage"),
            })
            if len(selected) >= limit:
                break
    return selected


async def _analytics_video_rows_for_id(start: date, end: date, video_id: str,
                                       content_type: str) -> list[dict]:
    token = await access_token()
    params = {
        "ids": "channel==MINE",
        "startDate": start.isoformat(),
        "endDate": end.isoformat(),
        "dimensions": "creatorContentType",
        "metrics": "views,averageViewPercentage",
        "filters": f"video=={video_id}",
        "maxResults": 10,
    }
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(
            ANALYTICS_API, params=params,
            headers={"Authorization": f"Bearer {token}"},
        )
        response.raise_for_status()
        data = response.json()
    headers = [h.get("name") for h in data.get("columnHeaders", [])]
    return [dict(zip(headers, row)) for row in data.get("rows", []) or []]


async def latest_long_video() -> dict | None:
    uploads = await recent_uploads(30)
    end = date.today() - timedelta(days=2)
    start = end - timedelta(days=27)
    for item in uploads:
        video_id = item.get("id")
        if not video_id:
            continue
        published = (item.get("snippet") or {}).get("publishedAt", "")[:10]
        start = date.fromisoformat(published) if published else end - timedelta(days=89)
        if start > end:
            continue
        rows = await _analytics_video_rows_for_id(start, end, video_id, "VIDEO_ON_DEMAND")
        if rows:
            snippet = item.get("snippet", {})
            return {
                "id": video_id,
                "title": snippet.get("title", video_id),
                "published_at": snippet.get("publishedAt", ""),
                "url": f"https://www.youtube.com/watch?v={video_id}",
                "views": rows[0].get("views", 0),
                "averageViewPercentage": rows[0].get("averageViewPercentage"),
            }
    return None
