"""The local HTTP application; importing it never loads model weights."""

import platform
import secrets
import shutil
from typing import Annotated

from fastapi import FastAPI, File, Form, Query, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator
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


class RevisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expectedRevision: int = Field(ge=0, strict=True)


class GroupingRequest(RevisionRequest):
    segmentIds: list[str] | None = Field(default=None, min_length=1)

    @field_validator("segmentIds", mode="before")
    @classmethod
    def validate_selection(cls, value):
        if not isinstance(value, list) or any(not isinstance(sid, str) or not sid for sid in value):
            raise ValueError("Use a nonempty list of source segment IDs.")
        return value


class ProofreadingRequest(GroupingRequest):
    glossary: list[str] = Field(default_factory=list, max_length=30)

    @field_validator("glossary")
    @classmethod
    def validate_glossary(cls, value):
        if (
            any(not term.strip() or len(term.encode()) > 80 for term in value)
            or sum(len(term.encode()) for term in value) > 700
        ):
            raise ValueError("Use up to 30 short protected spellings, at most 700 UTF-8 bytes.")
        return value


class SuggestionRequest(RevisionRequest):
    segmentIds: list[str] = Field(min_length=1, max_length=10000)


class SplitRequest(RevisionRequest):
    beforeSegmentId: str = Field(min_length=1, strict=True)


def create_app(settings: Settings | None = None, storage: Storage | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    storage = storage or Storage(settings.data_root)
    storage.initialize()
    jobs = Jobs(storage)
    jobs.initialize()
    from .proofreading import Proofreading

    proofreading = Proofreading(jobs)
    app = FastAPI(title="LocalScribe", docs_url=None, redoc_url=None, openapi_url=None)
    app.state.settings = settings
    app.state.storage = storage
    app.state.jobs = jobs
    app.state.proofreading = proofreading
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
            "storage": {"availableBytes": disk.free, "dataRoot": str(settings.data_root)},
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
        references = {
            name: {key: models[name][key] for key in ("repo", "revision")}
            for name in required
            if models[name].get("repo") and models[name].get("revision")
        }
        return await import_upload(
            file, storage, settings_options.model_dump(), jobs, model_settings=references or None
        )

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
        for name, reference in job.get("modelSettings", {}).items():
            if any(models[name].get(key) != reference.get(key) for key in ("repo", "revision")):
                raise JobError(
                    409,
                    "model_revision_changed",
                    "Restore this recording's original model snapshots before retrying.",
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

    @app.get("/api/jobs/{job_id}/history")
    def history(job_id: str):
        return jobs.history(job_id)

    @app.post("/api/jobs/{job_id}/history/undo")
    def undo(job_id: str, body: RevisionRequest):
        return jobs.undo(job_id, body.expectedRevision)

    @app.post("/api/jobs/{job_id}/history/redo")
    def redo(job_id: str, body: RevisionRequest):
        return jobs.redo(job_id, body.expectedRevision)

    @app.post("/api/jobs/{job_id}/grouping/preview")
    def grouping_preview(job_id: str, body: GroupingRequest):
        return jobs.grouping_preview(job_id, body.expectedRevision, body.segmentIds)

    @app.post("/api/jobs/{job_id}/grouping/apply")
    def grouping_apply(job_id: str, body: GroupingRequest):
        return jobs.grouping_apply(job_id, body.expectedRevision, body.segmentIds)

    @app.post("/api/jobs/{job_id}/grouping/split")
    def grouping_split(job_id: str, body: SplitRequest):
        return jobs.grouping_split(job_id, body.expectedRevision, body.beforeSegmentId)

    @app.get("/api/proofreading/readiness")
    def proofreading_readiness():
        from .heavy import MARKER

        return {
            **proofreading.readiness(),
            "heavyWorkBlocked": MARKER.exists(),
            "recovery": "After an interrupted/failed model connection, unload the configured instance in LM Studio. Wait for LocalScribe to observe it unloaded before loading it again."
            if MARKER.exists()
            else None,
        }

    @app.post("/api/jobs/{job_id}/proofreading", status_code=202)
    def start_proofreading(job_id: str, body: ProofreadingRequest):
        return proofreading.create(job_id, body.expectedRevision, body.segmentIds, body.glossary)

    @app.get("/api/jobs/{job_id}/proofreading")
    def latest_proofreading(job_id: str):
        return proofreading.get(job_id)

    @app.post("/api/jobs/{job_id}/proofreading/{task_id}/cancel")
    def cancel_proofreading(job_id: str, task_id: str):
        return proofreading.cancel(job_id, task_id)

    @app.post("/api/jobs/{job_id}/proofreading/{task_id}/apply")
    def apply_proofreading(job_id: str, task_id: str, body: SuggestionRequest):
        return proofreading.apply(job_id, task_id, body.expectedRevision, body.segmentIds)

    @app.post("/api/jobs/{job_id}/proofreading/{task_id}/reject")
    def reject_proofreading(job_id: str, task_id: str, body: SuggestionRequest):
        return proofreading.reject(job_id, task_id, body.expectedRevision, body.segmentIds)

    @app.post("/api/jobs/{job_id}/local-files")
    def sync_local_files(job_id: str):
        return jobs.sync_local_files(job_id)

    @app.get("/api/jobs/{job_id}/export")
    def export(
        job_id: str,
        format: str = Query(...),
        source: str = Query("current"),
        layout: str = Query("grouped"),
    ):
        if format not in {"txt", "srt", "vtt", "json"}:
            raise JobError(422, "unsupported_export", "Choose TXT, SRT, VTT, or JSON.")
        if layout not in {"grouped", "segmented"}:
            raise JobError(422, "invalid_layout", "Choose grouped or segmented layout.")
        content, media_type = render(jobs.transcript(job_id, source), format, layout=layout)
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
