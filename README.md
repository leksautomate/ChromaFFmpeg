# ChromaFFmpeg

A self-hosted FFmpeg API with a built-in web UI. Submit media URLs or upload binary files, process them server-side with FFmpeg, and get back a persistent URL — no CLI required.

**Stack:** Python 3.11 · FastAPI · FFmpeg · Alpine.js · Docker

---

## Features

| Endpoint | What it does | Output |
|---|---|---|
| `POST /merge` | Merge video + audio with configurable length strategy | URL → MP4 |
| `POST /animate` | Apply Ken Burns, zoom, or pan effects to image or video | URL → MP4 |
| `POST /combine` | Concatenate multiple videos or audio files | URL → MP4 / MP3 |
| `POST /image-to-video` | Convert a static image to MP4 with optional animation | URL → MP4 |
| `POST /loop` | Repeat a video clip N times (stream copy, no re-encode) | URL → MP4 |
| `POST /concat-transitions` | Concatenate clips with xfade transitions between them | URL → MP4 |
| `POST /metadata` | Get duration, resolution, fps, bitrate, stream info | JSON |
| `POST /upload` | Upload any binary file and get back a persistent URL | JSON |
| `GET /folders` | List all named folders | JSON |
| `POST /folders` | Create a named folder | JSON |
| `GET /folders/{name}` | List files inside a folder | JSON |
| `DELETE /folders/{name}` | Delete a folder and all its files | JSON |
| `GET /folders/{name}/urls` | Get all file URLs in a folder as a /combine body | JSON |
| `DELETE /folders/{name}/{filename}` | Delete a single file from a folder | JSON |
| `GET /files` | List all job output files | JSON |
| `DELETE /files` | Purge all job output files | JSON |
| `DELETE /files/{job_id}` | Delete a single job's output | JSON |
| `GET /health` | Health check | JSON |

---

## Quick Start

### 1. Clone and configure

```bash
git clone https://github.com/you/chromaffmpeg.git
cd chromaffmpeg
cp .env.example .env
```

Edit `.env`:

```
API_KEY=your-secret-key-here
BASE_URL=http://your-vps-ip:9000
```

### 2. Run with Docker

```bash
mkdir -p /data/outputs /data/folders
docker compose up --build -d
```

The API and UI are live at `http://your-vps-ip:9000`

---

## Web UI

Open `http://your-vps-ip:9000` in your browser. Enter your API key in the sidebar — it is saved to `localStorage`.

**Processing:**

- **Merge** — paste a video URL and audio URL, choose a length mismatch strategy, get a merged MP4
- **Animate** — apply Ken Burns zoom or pan animation to an image or video
- **Combine** — concatenate multiple files into one (optional re-encode for mixed codecs)
- **Image to Video** — convert a static image to MP4 with optional animation
- **Loop** — repeat a video clip N times
- **Transitions** — concatenate clips with animated xfade transitions
- **Metadata** — inspect any media URL

**Storage:**

- **Upload** — drag-and-drop or browse to upload any binary file (video, audio, image) and get back a URL instantly; optionally save into a named folder
- **Folders** — create named collections, browse files inside each folder, preview inline, copy URLs, download, or delete
- **Storage** — browse all job output files, click any file to preview inline, copy URL, download, or purge

All result panels include an inline media preview, a copyable URL, and a download button. If an error occurs, a **▼ Show FFmpeg log** toggle reveals the raw FFmpeg stderr for diagnosis.

---

## API Reference

All endpoints require the header:

```
X-API-Key: your-secret-key
```

Interactive docs (Swagger UI): `http://your-vps-ip:9000/docs`

All processing endpoints return at minimum:

```json
{
  "url": "http://your-vps-ip:9000/files/{job_id}/output.mp4",
  "filename": "output.mp4",
  "job_id": "uuid"
}
```

Some endpoints include an optional `"warning"` field when a fallback was applied (see `/merge`).

---

### POST /merge

Merges a video and audio file. The `strategy` field controls how a length mismatch is handled.

**Request body:**

```json
{
  "video_url": "https://example.com/video.mp4",
  "audio_url": "https://example.com/audio.mp3",
  "strategy": "trim_or_slow",
  "folder": "MyProject"
}
```

`folder` is optional. When set, the output is saved into that named folder (case-sensitive, must exist — create it first via `POST /folders`) and the response returns a `/store/` URL instead of a `/files/` URL.

**`strategy` values:**

| Value | Video longer than audio | Audio longer than video |
|---|---|---|
| `trim_or_slow` *(default)* | Trim video to audio length — stream copy, fast | Slow video down to fill the audio duration |
| `speed_match` | Speed up video to match audio | Slow video down to match audio |
| `trim` | Cut at whichever stream ends first | Cut at whichever stream ends first |

**Duration detection fallback:** The server probes duration from the container header first, then falls back to stream-level headers. If duration cannot be determined for either file, the chosen strategy is skipped and `trim` (`-shortest`) is applied automatically. A `"warning"` field is added to the response:

```json
{
  "url": "...",
  "filename": "output.mp4",
  "job_id": "uuid",
  "warning": "Could not detect one or both media durations. video=unknown, audio=12.50s. Fell back to 'Trim to Shortest' — output ends when either stream ends."
}
```

**curl:**

```bash
# trim_or_slow — trim if video is longer, slow down if shorter
curl -X POST http://localhost:9000/merge \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-secret-key" \
  -d '{
    "video_url": "https://example.com/video.mp4",
    "audio_url": "https://example.com/audio.mp3",
    "strategy": "trim_or_slow"
  }'

# speed_match — stretch or compress video speed to fit audio exactly
curl -X POST http://localhost:9000/merge \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-secret-key" \
  -d '{
    "video_url": "https://example.com/video.mp4",
    "audio_url": "https://example.com/audio.mp3",
    "strategy": "speed_match"
  }'

# trim — cut at the shorter stream, no speed change
curl -X POST http://localhost:9000/merge \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-secret-key" \
  -d '{
    "video_url": "https://example.com/video.mp4",
    "audio_url": "https://example.com/audio.mp3",
    "strategy": "trim"
  }'

# save output directly to a named folder (MyProject must exist)
curl -X POST http://localhost:9000/merge \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-secret-key" \
  -d '{
    "video_url": "https://example.com/video.mp4",
    "audio_url": "https://example.com/audio.mp3",
    "strategy": "trim_or_slow",
    "folder": "MyProject"
  }'
```

**Response with folder:**
```json
{
  "url": "http://localhost:9000/store/MyProject/output.mp4",
  "filename": "output.mp4",
  "folder": "MyProject"
}
```

---

### POST /animate

Applies a cinematic animation effect to an image or video.

**Request body:**

```json
{
  "media_url": "https://example.com/photo.jpg",
  "media_type": "image",
  "animation": "zoom_in",
  "duration": 6,
  "fps": 25,
  "resolution": "1920x1080",
  "folder": "MyProject"
}
```

`folder` is optional — see [folder output](#folder-output) below.

**`animation` values:** `zoom_in` · `zoom_out` · `pan_left` · `pan_right` · `pan_zoom`

**`media_type` values:** `image` · `video`

**curl:**

```bash
# Animate an image
curl -X POST http://localhost:9000/animate \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-secret-key" \
  -d '{
    "media_url": "https://example.com/photo.jpg",
    "media_type": "image",
    "animation": "zoom_in",
    "duration": 6,
    "fps": 25,
    "resolution": "1920x1080"
  }'

# Save output to a named folder
curl -X POST http://localhost:9000/animate \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-secret-key" \
  -d '{
    "media_url": "https://example.com/photo.jpg",
    "media_type": "image",
    "animation": "pan_zoom",
    "duration": 8,
    "fps": 25,
    "resolution": "1920x1080",
    "folder": "MyProject"
  }'
```

---

### POST /combine

Concatenates multiple video or audio files into one.

**Request body:**

```json
{
  "type": "video",
  "urls": [
    "https://example.com/clip1.mp4",
    "https://example.com/clip2.mp4"
  ],
  "reencode": false,
  "folder": "MyProject"
}
```

`folder` is optional — see [folder output](#folder-output) below. Set `"type": "audio"` for MP3 output. Set `"reencode": true` for mixed-codec sources — slower but always compatible.

**curl:**

```bash
# Combine videos (stream copy — all clips must share codec/resolution)
curl -X POST http://localhost:9000/combine \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-secret-key" \
  -d '{
    "type": "video",
    "urls": ["https://example.com/clip1.mp4", "https://example.com/clip2.mp4"],
    "reencode": false
  }'

# Combine audio files
curl -X POST http://localhost:9000/combine \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-secret-key" \
  -d '{
    "type": "audio",
    "urls": ["https://example.com/part1.mp3", "https://example.com/part2.mp3"],
    "reencode": false
  }'

# Re-encode for mixed sources
curl -X POST http://localhost:9000/combine \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-secret-key" \
  -d '{
    "type": "video",
    "urls": ["https://example.com/clip1.mp4", "https://example.com/clip2.mov"],
    "reencode": true
  }'

# Save output to a named folder
curl -X POST http://localhost:9000/combine \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-secret-key" \
  -d '{
    "type": "video",
    "urls": ["https://example.com/clip1.mp4", "https://example.com/clip2.mp4"],
    "reencode": false,
    "folder": "MyProject"
  }'
```

---

### POST /image-to-video

Converts a static image to an MP4 video.

**Request body:**

```json
{
  "image_url": "https://example.com/photo.png",
  "duration": 8,
  "animation": "none",
  "fps": 25,
  "resolution": "1920x1080",
  "folder": "MyProject"
}
```

`folder` is optional — see [folder output](#folder-output) below.

**`animation` values:** `none` · `zoom_in` · `zoom_out` · `pan_left` · `pan_right` · `pan_zoom`

**curl:**

```bash
# Static image — no animation
curl -X POST http://localhost:9000/image-to-video \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-secret-key" \
  -d '{
    "image_url": "https://example.com/photo.png",
    "duration": 8,
    "animation": "none",
    "fps": 25,
    "resolution": "1920x1080"
  }'

# Ken Burns effect
curl -X POST http://localhost:9000/image-to-video \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-secret-key" \
  -d '{
    "image_url": "https://example.com/photo.png",
    "duration": 8,
    "animation": "pan_zoom",
    "fps": 25,
    "resolution": "1920x1080"
  }'

# Save output to a named folder
curl -X POST http://localhost:9000/image-to-video \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-secret-key" \
  -d '{
    "image_url": "https://example.com/photo.png",
    "duration": 8,
    "animation": "zoom_in",
    "fps": 25,
    "resolution": "1920x1080",
    "folder": "MyProject"
  }'
```

---

### POST /loop

Repeats a video clip N times by stream-copying — no re-encoding, near-instant.

**Request body:**

```json
{
  "video_url": "https://example.com/clip.mp4",
  "loop_count": 3,
  "folder": "MyProject"
}
```

`loop_count` must be between 2 and 50. `folder` is optional — see [folder output](#folder-output) below.

**curl:**

```bash
curl -X POST http://localhost:9000/loop \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-secret-key" \
  -d '{
    "video_url": "https://example.com/clip.mp4",
    "loop_count": 4
  }'

# Save looped output to a named folder
curl -X POST http://localhost:9000/loop \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-secret-key" \
  -d '{
    "video_url": "https://example.com/clip.mp4",
    "loop_count": 4,
    "folder": "MyProject"
  }'
```

---

### POST /concat-transitions

Concatenates video clips with smooth FFmpeg xfade transitions between them.

**Request body:**

```json
{
  "urls": [
    "https://example.com/clip1.mp4",
    "https://example.com/clip2.mp4",
    "https://example.com/clip3.mp4"
  ],
  "transition": "fade",
  "transition_duration": 1.0,
  "folder": "MyProject"
}
```

`folder` is optional — see [folder output](#folder-output) below.

**`transition` values:** `fade` · `fadeblack` · `fadewhite` · `dissolve` · `pixelize` · `wipeleft` · `wiperight` · `wipeup` · `wipedown` · `slideleft` · `slideright` · `smoothleft` · `smoothright` · `radial` · `circleopen` · `circleclose`

**Requirements:**
- All clips must share the same resolution and frame rate
- Duration must be detectable for all clips — required to calculate xfade offsets
- If all clips have audio, `acrossfade` transitions are applied to audio automatically; if any clip lacks audio the output is video-only

**curl:**

```bash
# Fade transition between three clips
curl -X POST http://localhost:9000/concat-transitions \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-secret-key" \
  -d '{
    "urls": [
      "https://example.com/clip1.mp4",
      "https://example.com/clip2.mp4",
      "https://example.com/clip3.mp4"
    ],
    "transition": "fade",
    "transition_duration": 1.0
  }'

# Wipe left with a shorter transition
curl -X POST http://localhost:9000/concat-transitions \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-secret-key" \
  -d '{
    "urls": [
      "https://example.com/clip1.mp4",
      "https://example.com/clip2.mp4"
    ],
    "transition": "wipeleft",
    "transition_duration": 0.5
  }'

# Save output to a named folder
curl -X POST http://localhost:9000/concat-transitions \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-secret-key" \
  -d '{
    "urls": [
      "https://example.com/clip1.mp4",
      "https://example.com/clip2.mp4",
      "https://example.com/clip3.mp4"
    ],
    "transition": "fade",
    "transition_duration": 1.0,
    "folder": "MyProject"
  }'
```

---

### Folder output

All processing endpoints (`/merge`, `/animate`, `/combine`, `/image-to-video`, `/loop`, `/concat-transitions`) accept an optional `"folder"` field in the request body.

When `folder` is set:
- The output file is copied into `/data/folders/{folder}/` (served at `/store/{folder}/`)
- The response returns a `/store/` URL and a `"folder"` key instead of `"job_id"`
- The folder **must already exist** — create it first with `POST /folders`
- Folder names are **case-sensitive** (`MyProject` ≠ `myproject`)
- If a file with the same name already exists in the folder, a suffix (`_1`, `_2`, …) is appended automatically

**Response shape (with folder):**
```json
{
  "url": "http://localhost:9000/store/MyProject/output.mp4",
  "filename": "output.mp4",
  "folder": "MyProject"
}
```

**Response shape (without folder — default):**
```json
{
  "url": "http://localhost:9000/files/uuid/output.mp4",
  "filename": "output.mp4",
  "job_id": "uuid"
}
```

---

### POST /metadata

Returns duration, format, resolution, fps, bitrate, and stream counts for any media URL.

**Request body:**

```json
{ "url": "https://example.com/video.mp4" }
```

**curl:**

```bash
curl -X POST http://localhost:9000/metadata \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-secret-key" \
  -d '{"url": "https://example.com/video.mp4"}'
```

**Response:**

```json
{
  "duration_seconds": 47.32,
  "duration_formatted": "0:00:47",
  "format": "mov,mp4,m4a,3gp,3g2,mj2",
  "size_bytes": 4823042,
  "video_streams": 1,
  "audio_streams": 1,
  "width": 1920,
  "height": 1080,
  "fps": 25.0,
  "bitrate_kbps": 2048
}
```

---

### POST /upload

Converts any binary file (video, audio, image, or anything else) into a persistent URL. Accepts multipart form data. Optionally saves into a named folder — if the folder does not exist it is created automatically.

**curl:**

```bash
# Upload to general job storage
curl -X POST http://localhost:9000/upload \
  -H "X-API-Key: your-secret-key" \
  -F "file=@/path/to/video.mp4"

# Upload into a named folder
curl -X POST http://localhost:9000/upload \
  -H "X-API-Key: your-secret-key" \
  -F "file=@/path/to/photo.jpg" \
  -F "folder=my-project"

# Upload an audio file into a folder
curl -X POST http://localhost:9000/upload \
  -H "X-API-Key: your-secret-key" \
  -F "file=@/path/to/track.mp3" \
  -F "folder=audio-assets"
```

**Response (no folder):**

```json
{
  "url": "http://your-vps-ip:9000/files/{job_id}/video.mp4",
  "filename": "video.mp4",
  "job_id": "uuid",
  "size_bytes": 4823042
}
```

**Response (with folder):**

```json
{
  "url": "http://your-vps-ip:9000/store/my-project/photo.jpg",
  "filename": "photo.jpg",
  "folder": "my-project",
  "size_bytes": 204800
}
```

Maximum file size: **500 MB**. If a file with the same name already exists in the folder, a numeric suffix is added automatically (`photo_1.jpg`, `photo_2.jpg`, …).

---

### GET /folders

List all named folders with file counts and total sizes.

**curl:**

```bash
curl http://localhost:9000/folders \
  -H "X-API-Key: your-secret-key"
```

**Response:**

```json
{
  "folders": [
    { "name": "my-project",   "file_count": 3, "total_size_bytes": 1048576 },
    { "name": "audio-assets", "file_count": 7, "total_size_bytes": 8388608 }
  ],
  "count": 2
}
```

---

### POST /folders

Create a named folder.

**curl:**

```bash
curl -X POST http://localhost:9000/folders \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-secret-key" \
  -d '{"name": "my-project"}'
```

**Response:**

```json
{ "name": "my-project", "created": true }
```

Folder names are sanitized — only alphanumeric characters, hyphens, and underscores are kept (max 64 chars). You can also create folders implicitly by passing `folder=name` in `POST /upload`.

---

### GET /folders/{name}

List all files inside a folder.

**curl:**

```bash
curl http://localhost:9000/folders/my-project \
  -H "X-API-Key: your-secret-key"
```

**Response:**

```json
{
  "folder": "my-project",
  "files": [
    {
      "filename": "photo.jpg",
      "url": "http://your-vps-ip:9000/store/my-project/photo.jpg",
      "size_bytes": 204800,
      "created_at": "2026-03-13T12:00:00"
    }
  ],
  "count": 1,
  "total_size_bytes": 204800
}
```

---

### GET /folders/{name}/urls

Returns all file URLs in a folder formatted as a ready-to-use body for `POST /combine`.

**Query parameters:**
- `type`: Either `video` (default) or `audio`.
- `reencode`: Boolean. Set `true` if you plan to combine files with different codecs.

**curl:**

```bash
curl "http://localhost:9000/folders/my-project/urls?type=video&reencode=false" \
  -H "X-API-Key: your-secret-key"
```

**Response:**

```json
{
  "type": "video",
  "urls": [
    "http://your-vps-ip:9000/store/my-project/clip1.mp4",
    "http://your-vps-ip:9000/store/my-project/clip2.mp4"
  ],
  "reencode": false,
  "count": 2
}
```

---

### DELETE /folders/{name}

Delete a folder and all files inside it permanently.

**curl:**

```bash
curl -X DELETE http://localhost:9000/folders/my-project \
  -H "X-API-Key: your-secret-key"
```

**Response:**

```json
{ "deleted": "my-project" }
```

---

### DELETE /folders/{name}/{filename}

Delete a single file from a folder.

**curl:**

```bash
curl -X DELETE http://localhost:9000/folders/my-project/photo.jpg \
  -H "X-API-Key: your-secret-key"
```

**Response:**

```json
{ "deleted": "photo.jpg", "folder": "my-project" }
```

---

### GET /files

List all stored job output files.

**curl:**

```bash
curl http://localhost:9000/files \
  -H "X-API-Key: your-secret-key"
```

**Response:**

```json
{
  "files": [
    {
      "job_id": "uuid",
      "filename": "output.mp4",
      "url": "http://your-vps-ip:9000/files/uuid/output.mp4",
      "size_bytes": 4823042,
      "created_at": "2026-03-13T12:00:00"
    }
  ],
  "count": 1,
  "total_size_bytes": 4823042
}
```

---

### DELETE /files

Purge all stored job output files.

**curl:**

```bash
curl -X DELETE http://localhost:9000/files \
  -H "X-API-Key: your-secret-key"
```

**Response:**

```json
{ "deleted_jobs": 12, "message": "Purged 12 job(s)" }
```

---

### DELETE /files/{job_id}

Delete a single job's output directory.

**curl:**

```bash
curl -X DELETE http://localhost:9000/files/uuid \
  -H "X-API-Key: your-secret-key"
```

**Response:**

```json
{ "deleted": "uuid" }
```

---

### GET /health

```bash
curl http://localhost:9000/health
```

```json
{ "status": "ok" }
```

---

## Error Handling

All errors return a JSON body with a consistent shape:

```json
{
  "detail": {
    "error": "FFmpeg processing failed",
    "detail": "...raw FFmpeg stderr output..."
  }
}
```

The web UI surfaces the `error` message directly. A **▼ Show FFmpeg log** toggle reveals the full stderr so you can diagnose the root cause without touching the server.

**Common FFmpeg errors and fixes:**

| Error | Cause | Fix |
|---|---|---|
| `No such file or directory` | Input URL unreachable or wrong path | Verify the URL is publicly accessible |
| `Invalid data found when processing input` | Corrupted or unsupported container | Re-download or convert the source file |
| `height not divisible by 2` | Odd pixel dimensions | Add `-vf scale=trunc(iw/2)*2:trunc(ih/2)*2` |
| `Encoder libx264 not found` | FFmpeg binary missing codec | Use the full FFmpeg Docker image |
| `Output file is empty` | Silent failure — usually a filter error | Expand the FFmpeg log in the UI |
| xfade `Could not determine duration` | Clip has no duration metadata | Pre-process with `/metadata` to verify, or re-encode the source |
| `HTTP 413` on `/upload` | File exceeds 500 MB limit | Compress or split the file first |

All FFmpeg and ffprobe errors are logged server-side (Python `logging`) with the full command line and stderr tail for every failed job.

---

## Storage

There are two independent storage areas:

| Area | Path (container) | Served at | Purpose |
|---|---|---|---|
| Job outputs | `/data/outputs/{uuid}/` | `/files/{uuid}/{filename}` | Results from processing endpoints |
| Named folders | `/data/folders/{name}/` | `/store/{name}/{filename}` | Uploaded files organized by folder |

Both are Docker volumes that persist across container restarts. Neither path requires authentication to read — the URL itself acts as the access token. Add a reverse proxy with authentication if you need access control.

Create both directories on the host before starting:

```bash
mkdir -p /data/outputs /data/folders
```

---

## Configuration

| Variable | Description | Default |
|---|---|---|
| `API_KEY` | Required. Secret key sent in `X-API-Key` header | — |
| `BASE_URL` | Public base URL embedded in returned file URLs | `http://localhost:9000` |
| `OUTPUTS_DIR` | Directory for job output files inside the container | `/data/outputs` |
| `FOLDERS_DIR` | Directory for named folder files inside the container | `/data/folders` |

---

## Project Structure

```
chromaffmpeg/
├── app/
│   ├── main.py               # FastAPI app, router registration, static mounts
│   ├── auth.py               # API key header verification
│   ├── routes/
│   │   ├── merge.py          # Merge video + audio (trim_or_slow / speed_match / trim)
│   │   ├── animate.py        # Ken Burns / zoom / pan effects
│   │   ├── combine.py        # Concatenate multiple files
│   │   ├── image_to_video.py # Image → MP4 with optional animation
│   │   ├── loop.py           # Repeat a clip N times via concat demuxer
│   │   ├── transitions.py    # xfade + acrossfade transitions
│   │   ├── metadata.py       # ffprobe media info
│   │   ├── upload.py         # Binary upload → persistent URL
│   │   ├── folders.py        # Named folder CRUD
│   │   └── files.py          # List / purge job outputs
│   └── utils/
│       ├── downloader.py     # Async chunked HTTP download
│       ├── ffmpeg.py         # FFmpeg/ffprobe subprocess wrappers + duration probing
│       ├── cleanup.py        # Job directory management
│       ├── folders.py        # Folder utilities (sanitize, create, list, delete)
│       └── url.py            # file_url() and folder_url() helpers
├── static/
│   ├── index.html            # Web UI (Alpine.js)
│   └── app.js                # Frontend state and API calls
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── .env.example
```

---

## Notes

- Output files and uploaded files are **never deleted automatically** — purge via the UI or the DELETE endpoints
- `/files/` and `/store/` routes are **unauthenticated** — the URL acts as the access token; add a reverse proxy with auth if needed
- The `zoompan` filter (`/animate`, `/image-to-video`) is CPU-intensive — a 6 s 1080p animation can take 30–90 s depending on hardware
- `/combine` with `reencode: false` requires all inputs to share the same codec, resolution, and sample rate; use `reencode: true` for mixed sources
- `/concat-transitions` requires all clips to share the same resolution and fps — the xfade filter errors if dimensions differ
- `/loop` uses the concat demuxer with stream copy — output is generated near-instantly regardless of loop count
- `/merge` duration probing tries the container header first, then falls back to stream-level headers; if both fail the response includes a `"warning"` and uses `-shortest` as a safe fallback
- `/upload` chunks file reads at 1 MB and enforces a 500 MB hard limit; name collisions in folders are resolved automatically with a numeric suffix
