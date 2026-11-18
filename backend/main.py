from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

ROOT_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = ROOT_DIR / "frontend"

app = FastAPI(
    title="WEBSPIDER API",
    description="A responsible workspace for crawling publicly accessible web pages.",
    version="0.1.0",
)

app.mount("/assets", StaticFiles(directory=FRONTEND_DIR), name="assets")


@app.get("/api/health", tags=["System"])
async def health_check() -> dict[str, str]:
    """Return the API service status."""
    return {"status": "ok", "service": "WEBSPIDER API", "version": "0.1.0"}


@app.get("/", include_in_schema=False)
async def home() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "index.html")
