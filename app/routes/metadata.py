import json
import logging
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.auth import verify_api_key
from app.utils.ffmpeg import run_ffprobe

logger = logging.getLogger(__name__)

router = APIRouter(dependencies=[Depends(verify_api_key)])


class MetadataRequest(BaseModel):
    url: str


@router.post("/metadata", tags=["media"], summary="Get media metadata (duration, resolution, fps, etc.)")
async def get_metadata(req: MetadataRequest):
    """
    Returns duration, format, resolution, fps, bitrate, and stream counts for any media URL.

    ```bash
    curl -X POST http://localhost:9000/metadata \\
      -H "Content-Type: application/json" \\
      -H "X-API-Key: your-secret-key" \\
      -d '{"url": "https://example.com/video.mp4"}'
    ```
    """
    output = await run_ffprobe([
        "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        req.url,
    ])

    try:
        data = json.loads(output)
    except json.JSONDecodeError as e:
        logger.error("ffprobe returned invalid JSON for %s: %s", req.url, e)
        raise HTTPException(status_code=500, detail={"error": "ffprobe returned invalid output"})

    fmt = data.get("format", {})
    streams = data.get("streams", [])

    video_streams = [s for s in streams if s.get("codec_type") == "video"]
    audio_streams = [s for s in streams if s.get("codec_type") == "audio"]
    first_video = video_streams[0] if video_streams else {}

    fps_raw = first_video.get("r_frame_rate", "0/1")
    try:
        num, den = fps_raw.split("/")
        fps = round(int(num) / int(den), 3) if int(den) != 0 else 0.0
    except Exception:
        fps = 0.0

    try:
        duration = float(fmt.get("duration", 0) or 0)
        size_bytes = int(fmt.get("size", 0) or 0)
        bitrate_kbps = round(int(fmt.get("bit_rate", 0) or 0) / 1000)
    except (TypeError, ValueError) as e:
        logger.error("Failed to parse numeric metadata fields for %s: %s", req.url, e)
        raise HTTPException(status_code=500, detail={"error": "Failed to parse media metadata"})

    return {
        "duration_seconds": round(duration, 3),
        "duration_formatted": str(timedelta(seconds=int(duration))),
        "format": fmt.get("format_name", "").split(",")[0],
        "size_bytes": size_bytes,
        "video_streams": len(video_streams),
        "audio_streams": len(audio_streams),
        "width": first_video.get("width"),
        "height": first_video.get("height"),
        "fps": fps,
        "bitrate_kbps": bitrate_kbps,
    }
