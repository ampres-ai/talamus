"""Local web workbench backend: a thin FastAPI bridge over talamus.services."""

from __future__ import annotations

from talamus.webapi.app import create_app

__all__ = ["create_app"]
