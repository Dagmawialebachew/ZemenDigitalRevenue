from __future__ import annotations

import io
import mimetypes
from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse, StreamingResponse

from backend.repositories.events import EventRepository

router = APIRouter(prefix="/api/public", tags=["public-media"])


@router.get("/product-media/{media_id}")
async def product_media(media_id: UUID, request: Request):
    async with request.app.state.db.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id,storage_type,value,mime_type,file_name FROM product_media WHERE id=$1 AND is_active=TRUE",
            media_id,
        )
    if row is None:
        raise HTTPException(status_code=404, detail="Media not found")
    if row["storage_type"] in {"url", "object_storage"} and str(row["value"]).startswith(("http://", "https://")):
        return RedirectResponse(str(row["value"]), status_code=307)
    if row["storage_type"] != "telegram_file_id":
        raise HTTPException(status_code=404, detail="Media is not browser-accessible")
    bot = request.app.state.bot
    if bot is None:
        raise HTTPException(status_code=503, detail="Telegram media gateway is unavailable")
    try:
        tg_file = await bot.get_file(row["value"])
        stream = io.BytesIO()
        await bot.download(row["value"], destination=stream)
        stream.seek(0)
        mime = row["mime_type"] or mimetypes.guess_type(row["file_name"] or tg_file.file_path or "media.bin")[0] or "application/octet-stream"
        filename = row["file_name"] or (tg_file.file_path or "media.bin").rsplit("/", 1)[-1]
        headers = {
            "Cache-Control": "public, max-age=3600, stale-while-revalidate=86400",
            "Content-Disposition": f"inline; filename*=UTF-8''{quote(filename)}",
            "Content-Length": str(stream.getbuffer().nbytes),
        }
        return StreamingResponse(stream, media_type=mime, headers=headers)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Could not load product media: {type(exc).__name__}") from None


@router.get("/m/{token}")
async def marketing_click(token: str, request: Request):
    # Per-recipient token: records a click without putting Telegram/user IDs in the URL.
    async with request.app.state.db.transaction() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM broadcast_click_links WHERE token=$1 FOR UPDATE", token
        )
        if row is None:
            raise HTTPException(status_code=404, detail="Link not found")
        await conn.execute(
            """UPDATE broadcast_click_links SET click_count=click_count+1,
                   first_clicked_at=COALESCE(first_clicked_at,now()),clicked_at=now(),updated_at=now()
               WHERE id=$1""", row["id"]
        )
        await conn.execute(
            """UPDATE broadcast_recipients SET clicked_at=COALESCE(clicked_at,now()),updated_at=now()
               WHERE broadcast_id=$1 AND user_id=$2""", row["broadcast_id"], row["user_id"]
        )
        await EventRepository().append(
            conn,event_type="BROADCAST_CLICKED",user_id=row["user_id"],
            payload={"broadcast_id":str(row["broadcast_id"]),"button_key":row["button_key"]},
        )
        destination = row["destination_url"]
    return RedirectResponse(str(destination), status_code=307)
