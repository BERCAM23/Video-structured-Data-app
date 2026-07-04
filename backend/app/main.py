import shutil
import uuid
from pathlib import Path
from typing import Callable

from fastapi import BackgroundTasks, FastAPI, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from app import chat, db, media, pipeline
from app.config import Settings, load_settings

ALLOWED_EXT = {".mp4", ".mov", ".mkv"}
MAX_DURATION_S = 3 * 3600
CHUNK = 1024 * 1024


def create_app(settings: Settings, db_path: Path,
               run_pipeline_fn: Callable[[str], None] | None = None) -> FastAPI:
    app = FastAPI(title="Fox Video Intelligence")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    conn = db.connect(db_path)
    db.init_db(conn)
    conn.close()

    if run_pipeline_fn is None:
        def run_pipeline_fn(video_id: str) -> None:
            pipeline.run_pipeline(video_id, settings, db_path)

    def get_conn():
        return db.connect(db_path)

    @app.post("/api/videos")
    async def upload_video(file: UploadFile, background_tasks: BackgroundTasks):
        ext = Path(file.filename or "").suffix.lower()
        if ext not in ALLOWED_EXT:
            raise HTTPException(400, f"unsupported file type: {ext or 'none'}")
        video_id = uuid.uuid4().hex[:12]
        vdir = settings.data_dir / "videos" / video_id
        vdir.mkdir(parents=True, exist_ok=True)
        dest = vdir / "source.mp4"
        with open(dest, "wb") as out:
            shutil.copyfileobj(file.file, out)
        try:
            duration = media.probe_duration(dest)
        except media.MediaError as e:
            dest.unlink(missing_ok=True)
            raise HTTPException(400, f"not a readable video: {e}")
        if duration > MAX_DURATION_S:
            dest.unlink(missing_ok=True)
            raise HTTPException(400, "video longer than 3 hours")
        conn = get_conn()
        db.create_video(conn, video_id, Path(file.filename).stem, "source.mp4")
        db.set_video_meta(conn, video_id, duration_s=duration)
        conn.close()
        background_tasks.add_task(run_pipeline_fn, video_id)
        return {"id": video_id}

    @app.get("/api/videos")
    def list_videos():
        conn = get_conn()
        rows = conn.execute(
            "SELECT id, title, status, duration_s, created_at FROM videos ORDER BY created_at DESC"
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    @app.get("/api/videos/{video_id}/status")
    def status(video_id: str):
        conn = get_conn()
        row = db.get_video(conn, video_id)
        conn.close()
        if row is None:
            raise HTTPException(404, "video not found")
        return {"id": row["id"], "status": row["status"],
                "error": row["error"], "duration_s": row["duration_s"]}

    @app.get("/api/videos/{video_id}")
    def records(video_id: str):
        conn = get_conn()
        rec = db.get_records(conn, video_id)
        conn.close()
        if rec["video"] is None:
            raise HTTPException(404, "video not found")
        return rec

    @app.get("/api/videos/{video_id}/stream")
    def stream_video(video_id: str, request: Request):
        path = settings.data_dir / "videos" / video_id / "source.mp4"
        if not path.exists():
            raise HTTPException(404, "video file not found")
        file_size = path.stat().st_size
        range_header = request.headers.get("range")
        start, end = 0, file_size - 1
        status_code = 200
        if range_header and range_header.startswith("bytes="):
            spec = range_header.removeprefix("bytes=").split("-")
            if spec[0]:
                start = int(spec[0])
            if len(spec) > 1 and spec[1]:
                end = min(int(spec[1]), file_size - 1)
            status_code = 206

        def iterator():
            remaining = end - start + 1
            with open(path, "rb") as f:
                f.seek(start)
                while remaining > 0:
                    data = f.read(min(CHUNK, remaining))
                    if not data:
                        break
                    remaining -= len(data)
                    yield data

        headers = {
            "Accept-Ranges": "bytes",
            "Content-Length": str(end - start + 1),
        }
        if status_code == 206:
            headers["Content-Range"] = f"bytes {start}-{end}/{file_size}"
        return StreamingResponse(iterator(), status_code=status_code,
                                 media_type="video/mp4", headers=headers)

    @app.post("/api/videos/{video_id}/chat")
    async def chat_endpoint(video_id: str, body: dict):
        conn = get_conn()
        rec = db.get_records(conn, video_id)
        conn.close()
        if rec["video"] is None:
            raise HTTPException(404, "video not found")
        if rec["video"]["status"] != "ready":
            raise HTTPException(409, "video is still processing")
        messages = body.get("messages", [])
        if not messages:
            raise HTTPException(400, "messages required")
        gen = chat.stream_chat(settings.anthropic_api_key, rec, messages)
        return StreamingResponse(gen, media_type="text/plain; charset=utf-8")

    return app


def build() -> FastAPI:
    settings = load_settings()
    return create_app(settings, settings.data_dir / "vault.db")
