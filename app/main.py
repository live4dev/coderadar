from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, RedirectResponse
from contextlib import asynccontextmanager
from pathlib import Path

from app.core.logging import setup_logging
from app.core.config import settings
from app.api.router import api_router

_STATIC_DIR = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    yield


app = FastAPI(
    title="CodeRadar",
    description="Technical profiling service for Git repositories (Bitbucket & GitLab)",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


@app.get("/health", tags=["health"])
def health():
    return {"status": "ok", "version": "0.1.0"}


@app.get("/ui", include_in_schema=False)
def ui():
    return FileResponse(_STATIC_DIR / "index.html")


@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse("/ui")


# Mount static assets (CSS/JS if ever added alongside index.html)
app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")
