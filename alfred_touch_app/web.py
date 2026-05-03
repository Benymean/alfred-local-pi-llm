from __future__ import annotations

import logging
from pathlib import Path
import uuid

from fastapi import BackgroundTasks, FastAPI, File, Form, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .api_models import ChatRequest
from .paths import FAVICON_PATH, STATIC_DIR, TEMPLATES_DIR
from .service import AlfredTouchService


logging.basicConfig(level=logging.INFO)


def create_app(service: AlfredTouchService | None = None) -> tuple[FastAPI, AlfredTouchService]:
    service = service or AlfredTouchService()
    templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

    app = FastAPI(title="Alfred Touch")
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
    app.mount("/alfred-audio", StaticFiles(directory=str(service.web_audio_dir)), name="alfred-audio")

    @app.on_event("startup")
    async def startup_cleanup() -> None:
        service.cleanup_old_audio()

    @app.get("/", response_class=HTMLResponse)
    async def read_root(request: Request):
        return templates.TemplateResponse(
            request=request,
            name="alfred_touch.html",
            context={"assistant_name": service.settings.assistant_name},
        )

    @app.get("/favicon.png")
    async def get_favicon():
        return FileResponse(str(FAVICON_PATH))

    @app.get("/api/bootstrap")
    async def get_bootstrap():
        return service.bootstrap_payload()

    @app.get("/api/health")
    async def get_health():
        return service.health_payload()

    @app.post("/api/diagnostics/speaker-test")
    async def speaker_test(background_tasks: BackgroundTasks):
        payload = service.test_speaker()
        background_tasks.add_task(service.cleanup_old_audio)
        return payload

    @app.post("/api/diagnostics/restart")
    async def restart_backend():
        return service.schedule_restart()

    @app.post("/api/chat")
    async def chat(request: ChatRequest, background_tasks: BackgroundTasks):
        payload = service.reply(request)
        background_tasks.add_task(service.cleanup_old_audio)
        return payload

    @app.post("/api/chat/stream")
    async def chat_stream(request: ChatRequest):
        generator = service.reply_stream(request)
        return StreamingResponse(
            generator,
            media_type="application/x-ndjson",
            headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
        )

    @app.post("/api/transcribe")
    async def transcribe(
        background_tasks: BackgroundTasks,
        audio: UploadFile = File(...),
        turn_id: str | None = Form(None),
        turn_started_at_ms: float | None = Form(None),
    ):
        suffix = Path(audio.filename or "recording.webm").suffix or ".webm"
        temp_path = service.web_audio_dir / f"upload_{uuid.uuid4().hex}{suffix}"
        try:
            with temp_path.open("wb") as buffer:
                while True:
                    chunk = await audio.read(1024 * 1024)
                    if not chunk:
                        break
                    buffer.write(chunk)
            text, perf = service.transcribe_upload(
                temp_path,
                turn_id=turn_id,
                turn_started_at_ms=turn_started_at_ms,
            )
            return {
                "text": text,
                "turn_id": perf["turn_id"],
                "timings": {
                    "stt_seconds": perf["stt_seconds"],
                    "end_to_end_seconds": perf["end_to_end_seconds"],
                },
            }
        finally:
            try:
                temp_path.unlink(missing_ok=True)
            except OSError:
                pass
            background_tasks.add_task(service.cleanup_old_audio)

    @app.post("/api/memory/reset")
    async def reset_memory():
        return service.reset_memory()

    return app, service


app, service = create_app()


def main() -> None:
    import os
    import uvicorn

    uvicorn.run(
        "alfred_touch:app",
        host=os.environ.get("ALFRED_TOUCH_HOST", "0.0.0.0"),
        port=int(os.environ.get("ALFRED_TOUCH_PORT", "8081")),
        reload=False,
    )
