import os
from urllib.parse import urlparse

import aiofiles
import httpx
from fastapi import HTTPException

from app.utils.url import get_base_url

CONTENT_TYPE_EXT = {
    "video/mp4": ".mp4",
    "video/quicktime": ".mov",
    "video/x-msvideo": ".avi",
    "video/webm": ".webm",
    "audio/mpeg": ".mp3",
    "audio/mp4": ".m4a",
    "audio/wav": ".wav",
    "audio/ogg": ".ogg",
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
}


def _ext_from_url(url: str) -> str:
    path = urlparse(url).path
    _, ext = os.path.splitext(path)
    return ext.lower() if ext else ""


async def download_file(url: str, dest_dir: str, filename_stem: str = "input") -> str:
    ext = _ext_from_url(url)
    dest_path = os.path.join(dest_dir, filename_stem + (ext or ".tmp"))

    # Include API key when downloading from own server
    headers = {}
    api_key = os.environ.get("API_KEY")
    if api_key and url.startswith(get_base_url()):
        headers["X-API-Key"] = api_key

    try:
        async with httpx.AsyncClient(timeout=120, follow_redirects=True, headers=headers) as client:
            async with client.stream("GET", url) as response:
                response.raise_for_status()

                if not ext:
                    content_type = response.headers.get("content-type", "").split(";")[0].strip()
                    inferred_ext = CONTENT_TYPE_EXT.get(content_type, ".tmp")
                    dest_path = os.path.join(dest_dir, filename_stem + inferred_ext)

                async with aiofiles.open(dest_path, "wb") as f:
                    async for chunk in response.aiter_bytes(chunk_size=65536):
                        await f.write(chunk)
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=400, detail={"error": f"Failed to download {url}: HTTP {e.response.status_code}"})
    except httpx.RequestError as e:
        raise HTTPException(status_code=400, detail={"error": f"Failed to download {url}: {str(e)}"})

    return dest_path
