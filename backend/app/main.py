from pathlib import Path

from fastapi import APIRouter, FastAPI, HTTPException, status
from fastapi.responses import FileResponse

from app.api import health
from app.settings import get_settings

API_PREFIX = "/api"

api_router = APIRouter(prefix=API_PREFIX)
api_router.include_router(health.router)


def _add_spa_routes(app: FastAPI, static_dir: Path) -> None:
    """Serve the built frontend; unknown non-API paths fall back to index.html."""
    root = static_dir.resolve()
    index_file = root / "index.html"
    api_segment = API_PREFIX.strip("/")

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa(full_path: str) -> FileResponse:
        # Registered after the API router, so this only sees API paths nobody handles:
        # those stay JSON 404s instead of returning the SPA shell.
        if full_path == api_segment or full_path.startswith(api_segment + "/"):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not Found")
        candidate = (root / full_path).resolve()
        if candidate.is_relative_to(root) and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(index_file)


def create_app(static_dir: Path | None = None) -> FastAPI:
    app = FastAPI(title="Sales Order Orchestrator")
    app.include_router(api_router)
    if static_dir is not None and (static_dir / "index.html").is_file():
        _add_spa_routes(app, static_dir)
    return app


app = create_app(get_settings().static_dir)
