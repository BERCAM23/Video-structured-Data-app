from fastapi.testclient import TestClient

from app import db
from app.config import Settings
from app.main import create_app


def make_client(tmp_path, tiny_clip=None):
    settings = Settings("k1", "k2", "k3", tmp_path / "data")
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    db_path = settings.data_dir / "vault.db"
    started: list[str] = []
    app = create_app(settings, db_path, run_pipeline_fn=lambda vid: started.append(vid))
    return TestClient(app), settings, db_path, started


def test_upload_starts_pipeline(tmp_path, tiny_clip):
    client, settings, db_path, started = make_client(tmp_path)
    with open(tiny_clip, "rb") as f:
        resp = client.post("/api/videos", files={"file": ("partido.mp4", f, "video/mp4")})
    assert resp.status_code == 200
    vid = resp.json()["id"]
    assert started == [vid]
    assert (settings.data_dir / "videos" / vid / "source.mp4").exists()
    status = client.get(f"/api/videos/{vid}/status").json()
    assert status["status"] == "uploaded"
    assert status["duration_s"] > 0


def test_upload_rejects_bad_extension(tmp_path):
    client, *_ = make_client(tmp_path)
    resp = client.post("/api/videos", files={"file": ("nota.txt", b"hola", "text/plain")})
    assert resp.status_code == 400


def test_records_and_404(tmp_path):
    client, settings, db_path, _ = make_client(tmp_path)
    assert client.get("/api/videos/nope").status_code == 404
    conn = db.connect(db_path)
    db.init_db(conn)
    db.create_video(conn, "v1", "t", "source.mp4")
    body = client.get("/api/videos/v1").json()
    assert body["video"]["id"] == "v1"
    assert body["transcript_segments"] == []


def test_list_videos(tmp_path):
    client, settings, db_path, _ = make_client(tmp_path)
    assert client.get("/api/videos").json() == []
    conn = db.connect(db_path)
    db.init_db(conn)
    db.create_video(conn, "v1", "Partido", "source.mp4")
    items = client.get("/api/videos").json()
    assert items[0]["id"] == "v1"
    assert items[0]["status"] == "uploaded"


def test_search_empty(tmp_path):
    client, *_ = make_client(tmp_path)
    resp = client.get("/api/search", params={"q": "nada por aqui"})
    assert resp.status_code == 200
    assert resp.json() == {"results": []}


def test_chat_400_on_empty_messages(tmp_path):
    client, *_ = make_client(tmp_path)
    resp = client.post("/api/chat", json={"messages": []})
    assert resp.status_code == 400


def test_stream_supports_range(tmp_path, tiny_clip):
    client, settings, db_path, _ = make_client(tmp_path)
    with open(tiny_clip, "rb") as f:
        vid = client.post("/api/videos", files={"file": ("a.mp4", f, "video/mp4")}).json()["id"]
    full = client.get(f"/api/videos/{vid}/stream")
    assert full.status_code == 200
    partial = client.get(f"/api/videos/{vid}/stream", headers={"Range": "bytes=0-99"})
    assert partial.status_code == 206
    assert len(partial.content) == 100
    assert partial.headers["Content-Range"].startswith("bytes 0-99/")
