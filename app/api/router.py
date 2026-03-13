from fastapi import APIRouter
from app.api.v1 import projects, repositories, scans, developers, modules, analytics

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(projects.router)
api_router.include_router(repositories.router)
api_router.include_router(scans.router)
api_router.include_router(developers.router)
api_router.include_router(modules.router)
api_router.include_router(analytics.router)
