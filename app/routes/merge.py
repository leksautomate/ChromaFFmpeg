import logging
import os
import secrets
from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel

logger = logging.getLogger(__name__)

from app.auth import verify_api_key
from app.utils.cleanup import cleanup_job_dir, make_job_dir
from app.utils.downloader import download_file
from app.utils.ffmpeg import probe_duration, run_ffmpeg
from app.utils.folders import resolve_output

router = APIRouter(dependencies=[Depends(verify_api_key)])


class MergeRequest(BaseModel):
    video_url: str
    audio_url: str
    strategy: Literal["speed_match", "trim_or_slow", "trim"] = "speed_match"
    folder: str | None = None


@router.post("/merge", tags=["processing"], summary="Merge video and audio")
async def merge_audio_video(req: MergeRequest):
    """
    Merge a video file and an audio file. The `strategy` controls how length mismatches are handled.

    | strategy | video > audio | audio > video |
    |---|---|---|
    | `trim_or_slow` (default) | Trim video to audio length | Slow video to fill audio |
    | `speed_match` | Speed/slow video to match audio exactly | Speed/slow video to match audio |
    | `trim` | Cut at the shorter stream | Cut at the shorter stream |

    **Basic merge (trim_or_slow):**
    ```bash
    curl -X POST http://localhost:9000/merge \\
      -H "Content-Type: application/json" \\
      -H "X-API-Key: your-secret-key" \\
      -d '{
        "video_url": "https://example.com/video.mp4",
        "audio_url": "https://example.com/audio.mp3",
        "strategy": "trim_or_slow"
      }'
    ```

    **Save output to a named folder:**
    ```bash
    curl -X POST http://localhost:9000/merge \\
      -H "Content-Type: application/json" \\
      -H "X-API-Key: your-secret-key" \\
      -d '{
        "video_url": "https://example.com/video.mp4",
        "audio_url": "https://example.com/audio.mp3",
        "strategy": "trim_or_slow",
        "folder": "MyProject"
      }'
    ```
    """
    job_dir = make_job_dir()
    try:
        video_path = await download_file(req.video_url, job_dir, "video")
        audio_path = await download_file(req.audio_url, job_dir, "audio")

        video_dur = await probe_duration(video_path)
        audio_dur = await probe_duration(audio_path)

        output_filename = secrets.token_hex(8) + ".mp4"
        output_path = os.path.join(job_dir, output_filename)
        warning: str | None = None

        durations_known = video_dur is not None and audio_dur is not None

        if not durations_known:
            warning = (
                "Could not detect one or both media durations. "
                f"video={'unknown' if video_dur is None else f'{video_dur:.2f}s'}, "
                f"audio={'unknown' if audio_dur is None else f'{audio_dur:.2f}s'}. "
                "Fell back to 'Trim to Shortest' — output ends when either stream ends."
            )
            await run_ffmpeg([
                "-y", "-i", video_path, "-i", audio_path,
                "-map", "0:v:0", "-map", "1:a:0",
                "-c:v", "copy", "-c:a", "copy", "-shortest",
                output_path,
            ])

        elif req.strategy == "trim":
            await run_ffmpeg([
                "-y", "-i", video_path, "-i", audio_path,
                "-map", "0:v:0", "-map", "1:a:0",
                "-c:v", "copy", "-c:a", "copy", "-shortest",
                output_path,
            ])

        elif req.strategy == "trim_or_slow":
            if video_dur > audio_dur:
                await run_ffmpeg([
                    "-y", "-i", video_path, "-i", audio_path,
                    "-map", "0:v:0", "-map", "1:a:0",
                    "-t", f"{audio_dur:.6f}",
                    "-c:v", "copy", "-c:a", "copy",
                    output_path,
                ])
            elif audio_dur > video_dur:
                pts_expr = f"{audio_dur / video_dur:.6f}"
                await run_ffmpeg([
                    "-y", "-i", video_path, "-i", audio_path,
                    "-map", "0:v:0", "-map", "1:a:0",
                    "-filter:v", f"setpts={pts_expr}*PTS",
                    "-c:a", "copy", "-shortest",
                    output_path,
                ])
            else:
                await run_ffmpeg([
                    "-y", "-i", video_path, "-i", audio_path,
                    "-map", "0:v:0", "-map", "1:a:0",
                    "-c:v", "copy", "-c:a", "copy",
                    output_path,
                ])

        else:  # speed_match
            speed_factor = video_dur / audio_dur
            pts_expr = f"{1.0 / speed_factor:.6f}"
            await run_ffmpeg([
                "-y", "-i", video_path, "-i", audio_path,
                "-map", "0:v:0", "-map", "1:a:0",
                "-filter:v", f"setpts={pts_expr}*PTS",
                "-c:a", "copy", "-shortest",
                output_path,
            ])

        result = resolve_output(job_dir, output_filename, req.folder)
        if warning:
            result["warning"] = warning
        return result

    except Exception:
        cleanup_job_dir(job_dir)
        raise
