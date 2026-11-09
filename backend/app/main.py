from fastapi import APIRouter, FastAPI

from app.api import health

api_router = APIRouter(prefix="/api")
api_router.include_router(health.router)

app = FastAPI(title="Sales Order Orchestrator")
app.include_router(api_router)
