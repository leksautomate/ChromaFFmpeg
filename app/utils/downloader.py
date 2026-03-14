import os
import shutil
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


def _local_path_for_url(url: str) -> str | None:
    """
    If *url* refers to a file served by this server, return its local filesystem
    path so we can copy it directly without an HTTP round-trip.

    Handles:
      /store/{folder}/{filename}  → FOLDERS_DIR/{folder}/{filename}
      /files/{job_id}/{filename}  → OUTPUTS_DIR/{job_id}/{filename}
    """
    base = get_base_url().rstrip("/")
    if not url.startswith(base + "/"):
        return None

    # Lazy import to avoid circular dependency
    from app.utils.cleanup import OUTPUTS_DIR
    from app.utils.folders import FOLDERS_DIR

    rel = url[len(base):].lstrip("/")   # e.g. "store/upload/file.mp3"
    parts = rel.split("/")

    if len(parts) == 3 and parts[0] == "store":
        return os.path.join(FOLDERS_DIR, parts[1], parts[2])

    if len(parts) == 3 and parts[0] == "files":
        return os.path.join(OUTPUTS_DIR, parts[1], parts[2])

    return None


async def download_file(url: str, dest_dir: str, filename_stem: str = "input") -> str:
    ext = _ext_from_url(url)
    dest_path = os.path.join(dest_dir, filename_stem + (ext or ".tmp"))

    # ── Fast path: file lives on this server — copy from disk directly ────────
    local = _local_path_for_url(url)
    if local:
        if not os.path.isfile(local):
            raise HTTPException(
                status_code=400,
                detail={"error": f"File not found on server: {url}"},
            )
        shutil.copy2(local, dest_path)
        return dest_path

    # ── Remote download ───────────────────────────────────────────────────────
    try:
        async with httpx.AsyncClient(timeout=120, follow_redirects=True) as client:
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
