"""Aggregates all v1 routes. A future v2 gets its own router mounted under /api/v2."""

from fastapi import APIRouter

from app.api.routes import dashboard, events, health

api_v1_router = APIRouter()
api_v1_router.include_router(health.router)
api_v1_router.include_router(dashboard.router)
api_v1_router.include_router(events.router)
