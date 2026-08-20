from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
import structlog

log = structlog.get_logger(__name__)


def mount_static_apps(app: FastAPI, *, enabled: bool) -> None:
    """Mount production-built SPAs when present.

    Local development keeps Vite dev servers. The production Docker image builds
    both frontends and copies their dist directories into the application image.
    """
    if not enabled:
        return
    root = Path(__file__).resolve().parents[1]
    apps = (("/store", root / "miniapp" / "dist"), ("/control", root / "dashboard" / "dist"))
    for mount_path, directory in apps:
        if directory.is_dir() and (directory / "index.html").exists():
            app.mount(mount_path, StaticFiles(directory=str(directory), html=True), name=mount_path.strip("/"))
            log.info("static_app_mounted", mount_path=mount_path, directory=str(directory))
        else:
            log.warning("static_app_missing", mount_path=mount_path, directory=str(directory))
