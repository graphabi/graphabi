"""Local-only report server."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse


def create_report_app(report_path: Path) -> FastAPI:
    app = FastAPI(title="GraphABI local report", docs_url=None, redoc_url=None)

    @app.get("/", include_in_schema=False)
    def index() -> FileResponse:
        return FileResponse(report_path)

    @app.get("/report.json", include_in_schema=False)
    def report_json() -> FileResponse:
        return FileResponse(report_path.with_name("report.json"), media_type="application/json")

    return app
