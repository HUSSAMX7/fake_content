"""FastAPI app for proposal generation."""

from __future__ import annotations

import asyncio
import logging
import os
import shutil
import sys
import tempfile
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask

from backend.pipeline import run_pipeline, template_has_markers

load_dotenv()

# Windows consoles often use cp1256; pack validators may print ASCII-safe status lines.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

logger = logging.getLogger(__name__)

DEFAULT_TEMPLATE_PATH = Path(__file__).resolve().parent / "defaults" / "good_template.docx"

MAX_RESOURCE_BYTES = 20 * 1024 * 1024
MAX_TEMPLATE_BYTES = 15 * 1024 * 1024
MAX_RESOURCES = 10
ALLOWED_RESOURCE_SUFFIXES = {".pdf", ".docx"}
ALLOWED_TEMPLATE_SUFFIXES = {".docx"}
DOCX_MEDIA_TYPE = (
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
)

app = FastAPI(title="صياغة — مولّد العروض الفنية", version="0.1.0")

cors_origins = [
    origin.strip()
    for origin in os.getenv(
        "CORS_ORIGINS",
        "http://localhost:3000,http://127.0.0.1:3000",
    ).split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _suffix(filename: str | None) -> str:
    return Path(filename or "").suffix.lower()


def _safe_name(filename: str | None, fallback: str) -> str:
    name = Path(filename or fallback).name
    return name if name else fallback


async def _save_upload(upload: UploadFile, dest: Path, max_bytes: int) -> None:
    size = 0
    with dest.open("wb") as handle:
        while True:
            chunk = await upload.read(1024 * 1024)
            if not chunk:
                break
            size += len(chunk)
            if size > max_bytes:
                raise ValueError(
                    f"الملف أكبر من الحد المسموح ({max_bytes // (1024 * 1024)} MB)."
                )
            handle.write(chunk)


def _cleanup_dir(path: Path) -> None:
    shutil.rmtree(path, ignore_errors=True)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/default-template")
def get_default_template() -> FileResponse:
    if not DEFAULT_TEMPLATE_PATH.is_file():
        raise HTTPException(status_code=500, detail="التمبلت الافتراضي غير متوفر على الخادم.")
    return FileResponse(
        path=DEFAULT_TEMPLATE_PATH,
        media_type=DOCX_MEDIA_TYPE,
        filename="التمبلت_الافتراضي.docx",
    )


@app.post("/api/generate")
async def generate(
    resources: list[UploadFile] = File(...),
    template: UploadFile | None = File(None),
) -> FileResponse:
    if not resources:
        raise HTTPException(status_code=400, detail="ارفع مورداً واحداً على الأقل (PDF أو DOCX).")

    if len(resources) > MAX_RESOURCES:
        raise HTTPException(
            status_code=400,
            detail=f"الحد الأقصى للموارد هو {MAX_RESOURCES} ملفات.",
        )

    for resource in resources:
        suffix = _suffix(resource.filename)
        if suffix not in ALLOWED_RESOURCE_SUFFIXES:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"نوع الملف غير مدعوم للموارد: {resource.filename or 'unknown'}. "
                    "استخدم PDF أو DOCX."
                ),
            )

    if template is not None and template.filename:
        if _suffix(template.filename) not in ALLOWED_TEMPLATE_SUFFIXES:
            raise HTTPException(status_code=400, detail="التمبلت يجب أن يكون ملف DOCX.")

    work_dir = Path(tempfile.mkdtemp(prefix="mujeeb_generate_"))
    try:
        resource_paths: list[Path] = []
        for index, resource in enumerate(resources):
            dest = work_dir / f"resource_{index}_{_safe_name(resource.filename, 'file.docx')}"
            try:
                await _save_upload(resource, dest, MAX_RESOURCE_BYTES)
            except ValueError as exc:
                _cleanup_dir(work_dir)
                raise HTTPException(status_code=400, detail=str(exc)) from exc
            finally:
                await resource.close()
            resource_paths.append(dest)

        if template is not None and template.filename:
            template_path = work_dir / f"template_{_safe_name(template.filename, 'template.docx')}"
            try:
                await _save_upload(template, template_path, MAX_TEMPLATE_BYTES)
            except ValueError as exc:
                _cleanup_dir(work_dir)
                raise HTTPException(status_code=400, detail=str(exc)) from exc
            finally:
                await template.close()
        else:
            if not DEFAULT_TEMPLATE_PATH.is_file():
                _cleanup_dir(work_dir)
                raise HTTPException(
                    status_code=500,
                    detail="التمبلت الافتراضي غير متوفر على الخادم.",
                )
            template_path = work_dir / "default_template.docx"
            shutil.copy2(DEFAULT_TEMPLATE_PATH, template_path)

        if not template_has_markers(template_path):
            _cleanup_dir(work_dir)
            raise HTTPException(
                status_code=422,
                detail=(
                    "التمبلت لا يحتوي على علامات @ و @@. "
                    "أضف تعليمات بالصيغة @الشرح@@ ثم أعد المحاولة."
                ),
            )

        output_path = work_dir / "proposal.docx"
        try:
            result_path = await asyncio.to_thread(
                run_pipeline,
                template_path,
                resource_paths,
                output_path,
            )
        except Exception as exc:
            logger.exception("Proposal generation failed")
            _cleanup_dir(work_dir)
            raise HTTPException(
                status_code=500,
                detail="فشل التوليد. تحقق من الملفات ومفتاح OpenAI ثم أعد المحاولة.",
            ) from exc

        return FileResponse(
            path=result_path,
            media_type=DOCX_MEDIA_TYPE,
            filename="proposal.docx",
            background=BackgroundTask(_cleanup_dir, work_dir),
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Unexpected generate error")
        _cleanup_dir(work_dir)
        raise HTTPException(
            status_code=500,
            detail="حدث خطأ غير متوقع أثناء التوليد.",
        ) from exc
