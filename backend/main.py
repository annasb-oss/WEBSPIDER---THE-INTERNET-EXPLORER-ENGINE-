from __future__ import annotations

import asyncio
import csv
import io
import os
import time
import uuid
from collections import defaultdict, deque
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator

from backend.crawler import CrawlError, CrawlJob, normalize_url, run_crawl

ROOT_DIR = __import__("pathlib").Path(__file__).resolve().parent.parent
FRONTEND_DIR = ROOT_DIR / "frontend"
app = FastAPI(
    title="WEBSPIDER API",
    description="Responsible public-web crawling, passive security checks and sourced claim reviews.",
    version="0.3.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://annasb-oss.github.io",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)
app.mount("/assets", StaticFiles(directory=FRONTEND_DIR), name="assets")
jobs: dict[str, CrawlJob] = {}
active_job_id: str | None = None
job_lock = asyncio.Lock()
request_windows: dict[str, deque[float]] = defaultdict(deque)

def enforce_rate_limit(request: Request) -> None:
    client_ip = request.client.host if request.client else "unknown"
    now = time.monotonic()
    window = request_windows[client_ip]
    while window and now - window[0] > 600:
        window.popleft()
    if len(window) >= 12:
        raise HTTPException(status_code=429, detail="Limite temporário atingido. Aguarde alguns minutos.")
    window.append(now)


class CrawlRequest(BaseModel):
    url: str
    max_pages: int = Field(default=25, ge=1, le=50)
    max_depth: int = Field(default=2, ge=0, le=3)

    @field_validator("url")
    @classmethod
    def validate_url(cls, value: str) -> str:
        return normalize_url(value)


class ClaimCheckRequest(BaseModel):
    claim: str = Field(min_length=12, max_length=1000)


@app.get("/api/health", tags=["System"])
async def health_check() -> dict[str, Any]:
    return {
        "status": "ok",
        "service": "WEBSPIDER API",
        "version": "0.3.0",
        "fact_check_provider": "Google Fact Check Tools" if os.getenv("GOOGLE_FACTCHECK_API_KEY") else "not_configured",
    }


@app.post("/api/claims/check", tags=["Fact-check"])
async def check_claim(request: ClaimCheckRequest, http_request: Request) -> dict[str, Any]:
    enforce_rate_limit(http_request)
    """Return published fact-check reviews; never infer truth from writing style."""
    api_key = os.getenv("GOOGLE_FACTCHECK_API_KEY")
    explorer_url = "https://toolbox.google.com/factcheck/explorer?q=" + __import__("urllib.parse", fromlist=["quote_plus"]).quote_plus(request.claim)
    if not api_key:
        return {
            "status": "provider_not_configured",
            "verdict": "Não verificado",
            "message": "A consulta automática ainda não está configurada. Nenhuma conclusão sobre a alegação pode ser feita.",
            "explorer_url": explorer_url,
            "reviews": [],
        }
    try:
        async with httpx.AsyncClient(timeout=12.0, trust_env=False, follow_redirects=False) as client:
            response = await client.get(
                "https://factchecktools.googleapis.com/v1alpha1/claims:search",
                params={"query": request.claim, "key": api_key, "pageSize": 10},
            )
            response.raise_for_status()
            payload = response.json()
    except (httpx.HTTPError, ValueError):
        raise HTTPException(status_code=502, detail="A base de checagem não respondeu. Tente novamente mais tarde.")
    reviews = []
    for claim in payload.get("claims", [])[:10]:
        for review in claim.get("claimReview", [])[:3]:
            reviews.append({
                "claim": claim.get("text", ""),
                "claimant": claim.get("claimant", ""),
                "publisher": (review.get("publisher") or {}).get("name", ""),
                "title": review.get("title", ""),
                "url": review.get("url", ""),
                "rating": (review.get("reviewRating", {}).get("textualRating") or review.get("reviewRating", {}).get("alternateName", "")),
                "review_date": review.get("reviewDate", ""),
            })
    return {
        "status": "results" if reviews else "no_match",
        "verdict": "Há checagens publicadas relacionadas" if reviews else "Nenhuma checagem correspondente encontrada",
        "message": "Os resultados abaixo são avaliações publicadas por organizações de checagem independentes. Compare a alegação, a data e o contexto; ausência de resultado não prova que seja verdadeira.",
        "explorer_url": explorer_url,
        "reviews": reviews,
    }


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


@app.get("/api/crawls/{job_id}/audit", tags=["Passive site audit"])
async def site_audit(job_id: str) -> dict:
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Execução não encontrada.")
    if job.status != "completed":
        raise HTTPException(status_code=409, detail="A exploração ainda não foi concluída.")
    findings = []
    for page in job.pages:
        for issue in page.get("security_issues", []):
            findings.append({
                "severity": issue["severity"],
                "code": issue["code"],
                "title": issue["title"],
                "detail": issue["detail"],
                "url": page["url"],
            })
    return {
        "status": "completed",
        "pages_checked": len(job.pages),
        "findings_count": len(findings),
        "findings": findings,
        "scope": "Verificações passivas de cabeçalhos e conteúdo observável. Não é um pentest e não confirma ausência de vulnerabilidades.",
    }


@app.get("/api/crawls/{job_id}/export.csv", tags=["Crawler"])
async def export_csv(job_id: str):
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Execução não encontrada.")
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=[
        "url", "title", "description", "text_preview", "depth", "links_found", "status_code", "security_issues"
    ])
    writer.writeheader()
    for page in job.pages:
        row = dict(page)
        row["security_issues"] = "; ".join(issue["code"] for issue in page.get("security_issues", []))
        writer.writerow({key: row.get(key, "") for key in writer.fieldnames})
    buffer.seek(0)
    return StreamingResponse(
        iter([buffer.getvalue()]), media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="webspider-{job_id[:8]}.csv"'},
    )


@app.get("/", include_in_schema=False)
async def home() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "index.html")
