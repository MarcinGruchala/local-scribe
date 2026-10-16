"""The local HTTP application; importing it never loads model weights."""

import platform
import secrets
import shutil
from typing import Annotated

from fastapi import FastAPI, File, Form, Query, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from starlette.exceptions import HTTPException
from starlette.staticfiles import StaticFiles

from .config import Settings
from .contracts import Options
from .exports import render
from .jobs import JobError, Jobs
from .media import MediaError, import_upload
from .models import readiness
from .security import LocalSecurityMiddleware
from .storage import Storage


class TranscriptEdit(BaseModel):
    model_config = ConfigDict(extra="forbid")
    revision: int = Field(ge=0, strict=True)
    texts: dict[str, str | None] = Field(default_factory=dict)
    names: dict[str, str] = Field(default_factory=dict)


def create_app(settings: Settings | None = None, storage: Storage | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    storage = storage or Storage(settings.data_root)
    storage.initialize()
    jobs = Jobs(storage)
    jobs.initialize()
    app = FastAPI(title="LocalScribe", docs_url=None, redoc_url=None, openapi_url=None)
    app.state.settings = settings
    app.state.storage = storage
    app.state.jobs = jobs
    app.state.readiness = lambda: readiness(settings.model_root)
    app.state.session_token = secrets.token_urlsafe(32)
    app.add_middleware(LocalSecurityMiddleware, port=settings.port, token=app.state.session_token)

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, exc: HTTPException):
        detail = (
            exc.detail
            if isinstance(exc.detail, dict)
            else {"code": "http_error", "message": str(exc.detail)}
        )
        return JSONResponse({"error": detail}, status_code=exc.status_code)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError):
        return JSONResponse(
            {"error": {"code": "invalid_request", "message": "Request fields are invalid."}},
            status_code=422,
        )

    @app.exception_handler(JobError)
    @app.exception_handler(MediaError)
    async def domain_error(request: Request, exc):
        return JSONResponse(
            {"error": {"code": exc.code, "message": exc.message}}, status_code=exc.status
        )

    @app.get("/api/session")
    def session():
        return {"token": app.state.session_token}

    @app.get("/api/health")
    def health():
        ffmpeg = shutil.which("ffmpeg")
        ffprobe = shutil.which("ffprobe")
        disk = shutil.disk_usage(settings.data_root)
        models = app.state.readiness()
        worker = getattr(app.state, "worker", None)
        worker_running = worker is None or worker.alive
        active = next(
            (
                job["id"]
                for job in jobs.list(limit=100)["jobs"]
                if job["status"]
                in {"preparing", "transcribing", "diarizing", "assembling", "cancelling"}
            ),
            None,
        )
        return {
            "status": "ok",
            "ready": bool(ffmpeg and ffprobe and models["fast"]["ready"] and worker_running),
            "dependencies": {"ffmpeg": bool(ffmpeg), "ffprobe": bool(ffprobe)},
            "models": models,
            "runtime": {"python": platform.python_version(), "architecture": platform.machine()},
            "storage": {"availableBytes": disk.free},
            "activeJob": active,
            "worker": None
            if worker is None
            else {
                "running": worker.alive,
                "message": None
                if worker.alive
                else "Local worker stopped. Restart the application to recover interrupted work.",
            },
        }

    @app.post("/api/jobs", status_code=201)
    async def create_job(
        file: Annotated[UploadFile, File()], options: Annotated[str, Form()] = "{}"
    ):
        try:
            settings_options = Options.model_validate_json(options)
        except (ValueError, ValidationError):
            await file.close()
            raise JobError(
                422,
                "invalid_options",
                "Choose valid language, profile, diarization, and speaker count settings.",
            )
        models = app.state.readiness()
        required = [settings_options.profile] + (
            ["diarization"] if settings_options.diarization else []
        )
        if any(not models[name]["ready"] for name in required):
            await file.close()
            raise JobError(
                409,
                "model_not_ready",
                "Required local models are missing. Run explicit model setup and doctor.",
            )
        return await import_upload(file, storage, settings_options.model_dump(), jobs)

    @app.get("/api/jobs")
    def list_jobs(limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0)):
        return jobs.list(limit, offset)

    @app.get("/api/jobs/{job_id}")
    def job_detail(job_id: str):
        return jobs.get(job_id)

    @app.post("/api/jobs/{job_id}/cancel")
    def cancel(job_id: str):
        return jobs.cancel(job_id)

    @app.post("/api/jobs/{job_id}/retry")
    def retry(job_id: str):
        job = jobs.get(job_id)
        models = app.state.readiness()
        required = [job["options"]["profile"]] + (
            ["diarization"] if job["options"]["diarization"] else []
        )
        if any(not models[name]["ready"] for name in required):
            raise JobError(
                409,
                "model_not_ready",
                "Required local models are missing. Run explicit model setup and doctor.",
            )
        return jobs.retry(job_id)

    @app.get("/api/jobs/{job_id}/media")
    def media(job_id: str):
        return FileResponse(jobs.media_path(job_id), media_type="audio/wav")

    @app.get("/api/jobs/{job_id}/transcript")
    def transcript(job_id: str):
        return jobs.transcript(job_id)

    @app.patch("/api/jobs/{job_id}/transcript")
    def edit_transcript(job_id: str, edit: TranscriptEdit):
        return jobs.patch(job_id, edit.revision, edit.texts, edit.names)

    @app.get("/api/jobs/{job_id}/export")
    def export(job_id: str, format: str = Query(...)):
        if format not in {"txt", "srt", "vtt", "json"}:
            raise JobError(422, "unsupported_export", "Choose TXT, SRT, VTT, or JSON.")
        content, media_type = render(jobs.transcript(job_id), format)
        from fastapi.responses import Response

        return Response(
            content,
            media_type=media_type,
            headers={
                "Content-Disposition": f'attachment; filename="localscribe-{job_id}.{format}"'
            },
        )

    @app.delete("/api/jobs/{job_id}", status_code=204)
    def delete(job_id: str):
        jobs.delete(job_id)

    if (settings.frontend_dist / "assets").is_dir():
        app.mount(
            "/assets", StaticFiles(directory=settings.frontend_dist / "assets"), name="assets"
        )

    @app.get("/")
    def index():
        index_path = settings.frontend_dist / "index.html"
        if not index_path.is_file():
            return JSONResponse(
                {
                    "error": {
                        "code": "frontend_not_built",
                        "message": "Build the frontend with make build before starting LocalScribe.",
                    }
                },
                status_code=503,
            )
        return FileResponse(index_path)

    return app
