from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config import ROOT
from app.api.dashboard import router as dashboard_router
from app.api.routes import router


app = FastAPI(title="TraceGuard")
app.include_router(router)
app.include_router(dashboard_router)


@app.get("/api/{path:path}")
def unsupported_api_path(path: str) -> None:
    raise HTTPException(status_code=404, detail="Dashboard API endpoint not found")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


class SPAStaticFiles(StaticFiles):
    async def get_response(self, path, scope):
        try:
            return await super().get_response(path, scope)
        except StarletteHTTPException as exc:
            if exc.status_code == 404 and "." not in Path(path).name:
                return await super().get_response("index.html", scope)
            raise


frontend_dist = ROOT / "frontend/dist"
if frontend_dist.is_dir():
    app.mount("/", SPAStaticFiles(directory=frontend_dist, html=True), name="frontend")
