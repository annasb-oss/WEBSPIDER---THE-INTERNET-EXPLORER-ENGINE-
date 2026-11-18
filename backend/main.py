from __future__ import annotations

import asyncio
import csv
import io
import uuid
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator

from backend.crawler import CrawlError, CrawlJob, normalize_url, run_crawl

ROOT_DIR = __import__("pathlib").Path(__file__).resolve().parent.parent
FRONTEND_DIR = ROOT_DIR / "frontend"
app = FastAPI(
    title="WEBSPIDER API",
    description="Responsible crawling of publicly accessible pages.",
    version="0.2.0",
)
app.mount("/assets", StaticFiles(directory=FRONTEND_DIR), name="assets")
jobs: dict[str, CrawlJob] = {}
active_job_id: str | None = None
job_lock = asyncio.Lock()


class CrawlRequest(BaseModel):
    url: str
    max_pages: int = Field(default=25, ge=1, le=50)
    max_depth: int = Field(default=2, ge=0, le=3)

    @field_validator("url")
    @classmethod
    def validate_url(cls, value: str) -> str:
        return normalize_url(value)


@app.get("/api/health", tags=["System"])
async def health_check() -> dict[str, str]:
    return {"status": "ok", "service": "WEBSPIDER API", "version": "0.2.0"}


@app.post("/api/crawls", tags=["Crawler"])
async def start_crawl(request: CrawlRequest) -> dict:
    global active_job_id
    async with job_lock:
        if active_job_id and jobs.get(active_job_id) and jobs[active_job_id].status in {"queued", "running"}:
            raise HTTPException(status_code=409, detail="Já existe uma exploração em andamento.")
        job = CrawlJob(
            id=str(uuid.uuid4()), start_url=request.url,
            max_pages=request.max_pages, max_depth=request.max_depth,
        )
        jobs[job.id] = job
        active_job_id = job.id
        asyncio.create_task(run_crawl(job, jobs))
    return job.snapshot()


@app.get("/api/crawls/{job_id}", tags=["Crawler"])
async def crawl_status(job_id: str) -> dict:
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Execução não encontrada.")
    return job.snapshot()


@app.get("/api/crawls/{job_id}/export.csv", tags=["Crawler"])
async def export_csv(job_id: str):
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Execução não encontrada.")
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=[
        "url", "title", "description", "text_preview", "depth", "links_found", "status_code"
    ])
    writer.writeheader()
    writer.writerows(job.pages)
    buffer.seek(0)
    return StreamingResponse(
        iter([buffer.getvalue()]), media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="webspider-{job_id[:8]}.csv"'},
    )


@app.get("/", include_in_schema=False)
async def home() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "index.html")
