from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel

import config
from database import clear_cache, init_db
from epub_processor import extract_blocks
from job_manager import JobConflictError, JobNotReadyError, SingleJobManager
from provider_tools import fetch_models, health_check, normalize_base_url
from providers import BUILTIN_PROVIDERS


MAX_UPLOAD_BYTES = 100 * 1024 * 1024
MIN_TEMPERATURE = 0.0
MAX_TEMPERATURE = 2.0
MIN_BATCH_SIZE = 1
MAX_BATCH_SIZE = 50
MIN_CONCURRENCY = 1
MAX_CONCURRENCY = 20
MIN_MAX_BLOCKS = 0
MAX_MAX_BLOCKS = 200_000


class ModelsRequest(BaseModel):
    base_url: str
    api_key: str


class HealthRequest(BaseModel):
    base_url: str
    api_key: str
    model: str
    target_language: str = config.DEFAULT_TARGET_LANGUAGE


async def read_epub_upload(file: UploadFile) -> bytes:
    filename = file.filename or ""
    if not filename.lower().endswith(".epub"):
        raise HTTPException(status_code=400, detail="Only .epub files are supported.")

    epub_bytes = await file.read()
    if not epub_bytes:
        raise HTTPException(status_code=400, detail="Uploaded EPUB is empty.")
    if len(epub_bytes) > MAX_UPLOAD_BYTES:
        limit_mb = MAX_UPLOAD_BYTES // (1024 * 1024)
        raise HTTPException(status_code=400, detail=f"EPUB file is too large. Maximum size is {limit_mb}MB.")
    return epub_bytes


def validate_job_parameters(temperature: float, batch_size: int, concurrency: int, max_blocks: int) -> None:
    if not MIN_TEMPERATURE <= temperature <= MAX_TEMPERATURE:
        raise HTTPException(status_code=400, detail="temperature must be between 0 and 2.")
    if not MIN_BATCH_SIZE <= batch_size <= MAX_BATCH_SIZE:
        raise HTTPException(status_code=400, detail="batch_size must be between 1 and 50.")
    if not MIN_CONCURRENCY <= concurrency <= MAX_CONCURRENCY:
        raise HTTPException(status_code=400, detail="concurrency must be between 1 and 20.")
    if not MIN_MAX_BLOCKS <= max_blocks <= MAX_MAX_BLOCKS:
        raise HTTPException(status_code=400, detail="max_blocks must be between 0 and 200000.")


def create_app(manager: SingleJobManager | None = None) -> FastAPI:
    init_db(config.DB_PATH)
    app = FastAPI(title="Paperford API")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.state.manager = manager or SingleJobManager()

    @app.get("/api/config")
    def get_config() -> dict:
        return {
            "providers": BUILTIN_PROVIDERS,
            "target_languages": config.TARGET_LANGUAGES,
            "defaults": {
                "model": config.MODEL,
                "temperature": config.TEMPERATURE,
                "batch_size": config.BATCH_SIZE,
                "concurrency": config.CONCURRENCY,
                "max_blocks": 0,
                "target_language": config.DEFAULT_TARGET_LANGUAGE,
                "thinking_enabled": config.DEFAULT_THINKING_ENABLED,
            },
        }

    @app.post("/api/models")
    def get_models(request: ModelsRequest) -> dict:
        models, error = fetch_models(request.base_url, request.api_key)
        if models is None:
            return {"ok": False, "models": [], "error": error}
        return {"ok": True, "models": models, "error": None}

    @app.post("/api/health")
    def post_health(request: HealthRequest) -> dict:
        return health_check(
            request.base_url,
            request.api_key,
            request.model,
            request.target_language,
        )

    @app.post("/api/preview")
    async def preview(file: UploadFile = File(...)) -> dict:
        epub_bytes = await read_epub_upload(file)
        try:
            blocks = extract_blocks(epub_bytes)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Failed to parse EPUB: {exc}") from exc
        return {
            "total_blocks": len(blocks),
            "preview": [
                {
                    "block_id": block["block_id"],
                    "tag": block["tag"],
                    "text": block["text"][:240],
                }
                for block in blocks[:8]
            ],
        }

    @app.post("/api/extract-glossary")
    async def extract_glossary_api(
        file: UploadFile = File(...),
        api_key: str = Form(...),
        base_url: str = Form(...),
        model: str = Form(...),
        target_language: str = Form(config.DEFAULT_TARGET_LANGUAGE),
        thinking_enabled: bool = Form(config.DEFAULT_THINKING_ENABLED),
    ) -> dict:
        epub_bytes = await read_epub_upload(file)
        try:
            from translator import generate_glossary
            blocks = extract_blocks(epub_bytes)
            if not blocks:
                return {"glossary": ""}
            
            glossary_text = await generate_glossary(
                blocks=blocks,
                api_key=api_key,
                base_url=normalize_base_url(base_url),
                model=model,
                target_language=target_language,
                thinking_enabled=thinking_enabled,
            )
            return {"glossary": glossary_text}
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Failed to extract glossary: {exc}") from exc

    @app.post("/api/jobs")
    async def create_job(
        file: UploadFile = File(...),
        api_key: str = Form(...),
        base_url: str = Form(...),
        model: str = Form(...),
        temperature: float = Form(config.TEMPERATURE),
        batch_size: int = Form(config.BATCH_SIZE),
        concurrency: int = Form(config.CONCURRENCY),
        custom_prompt: str = Form(""),
        glossary: str = Form(""),
        target_language: str = Form(config.DEFAULT_TARGET_LANGUAGE),
        thinking_enabled: bool = Form(config.DEFAULT_THINKING_ENABLED),
        max_blocks: int = Form(0),
    ) -> dict:
        validate_job_parameters(temperature, batch_size, concurrency, max_blocks)
        epub_bytes = await read_epub_upload(file)
        try:
            return await app.state.manager.create_job(
                epub_bytes=epub_bytes,
                input_name=file.filename or "book.epub",
                api_key=api_key,
                base_url=normalize_base_url(base_url),
                model=model,
                temperature=temperature,
                batch_size=batch_size,
                concurrency=concurrency,
                custom_prompt=custom_prompt,
                glossary=glossary,
                target_language=target_language,
                thinking_enabled=thinking_enabled,
                max_blocks=max_blocks,
            )
        except JobConflictError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Failed to create job: {exc}") from exc

    @app.get("/api/jobs/current")
    def current_job() -> dict:
        return app.state.manager.snapshot()

    @app.post("/api/jobs/current/pause")
    async def pause_job() -> dict:
        return app.state.manager.pause()

    @app.post("/api/jobs/current/resume")
    async def resume_job() -> dict:
        return app.state.manager.resume()

    @app.post("/api/jobs/current/stop")
    async def stop_job() -> dict:
        return app.state.manager.stop()

    @app.post("/api/jobs/current/retry-failures")
    async def retry_failures() -> dict:
        return app.state.manager.retry_failures()

    @app.get("/api/jobs/current/download")
    def download() -> Response:
        try:
            output_bytes, output_name = app.state.manager.download_bytes()
        except JobNotReadyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return Response(
            output_bytes,
            media_type="application/epub+zip",
            headers={"Content-Disposition": f'attachment; filename="{output_name}"'},
        )

    @app.post("/api/cache/clear")
    def clear_translation_cache() -> dict:
        cleared = clear_cache(app.state.manager.db_path)
        return {"ok": True, "cleared": cleared}

    return app


app = create_app()
