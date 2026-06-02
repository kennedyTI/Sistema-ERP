"""
Entrada FastAPI da base Portal industria v2 sem dominio de Impressoras.

Mantem apenas o nucleo necessario nesta etapa:
- autenticacao Django Auth + JWT;
- resposta padrao;
- logging estruturado;
- logs/auditoria genericos.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException

from backend.app.core.config import APP_DESCRIPTION, APP_TITLE, APP_VERSION, get_cors_origins
from backend.app.core.exceptions import http_exception_handler, validation_exception_handler
from backend.app.core.logging import configure_logging
from backend.app.core.response import api_success
from backend.app.modules.auth.api import router as auth_router

configure_logging()

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):  # noqa: ARG001
    logger.info("[STARTUP] Iniciando Portal industria v2 base.")
    yield
    logger.info("[SHUTDOWN] Encerrando Portal industria v2 base.")


app = FastAPI(
    title=APP_TITLE,
    version=APP_VERSION,
    description=APP_DESCRIPTION,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)


# /api/v2 e a rota preferencial da base limpa. /api/v1 fica temporariamente
# como compatibilidade para clientes antigos de autenticacao.
app.include_router(auth_router, prefix="/api/v2")
app.include_router(auth_router, prefix="/api/v1")


@app.get("/")
def health_check():
    return api_success({"status": "ok"}, "API online")

