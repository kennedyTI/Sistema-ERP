"""
Configuracao comum da aplicacao FastAPI.
"""

from __future__ import annotations

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
BACKEND_DIR = Path(__file__).resolve().parents[2]

APP_TITLE = "Portal industria v2"
APP_VERSION = "2.0.0-base"
APP_DESCRIPTION = "Base modular sem dominio de Impressoras para reconstrucao gradual dos modulos."
DEFAULT_CORS_ORIGINS = "http://localhost:5173,http://localhost:5174"


def get_cors_origins() -> list[str]:
    raw_origins = os.getenv("BACKEND_CORS_ORIGINS", DEFAULT_CORS_ORIGINS)
    return [origin.strip() for origin in raw_origins.split(",") if origin.strip()]
