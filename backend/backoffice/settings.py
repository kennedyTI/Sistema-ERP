"""
Arquivo: backend/backoffice/settings.py

DescriÃ§Ã£o:
ConfiguraÃ§Ã£o do Django Admin separado do motor FastAPI.

Responsabilidades:
- Conectar no mesmo PostgreSQL do sistema
- Carregar variÃ¡veis do .env existente
- Preparar ambiente para admin local e futura dockerizaÃ§Ã£o
"""

import os
from pathlib import Path
from urllib.parse import unquote, urlparse

from dotenv import load_dotenv


# ---------------------------------------------------------------------
# ðŸ“Œ DIRETÃ“RIOS DO PROJETO
# ---------------------------------------------------------------------
PROJECT_DIR = Path(__file__).resolve().parents[2]
BACKEND_DIR = Path(__file__).resolve().parents[1]
ENV_PATH = BACKEND_DIR / ".env"


# ---------------------------------------------------------------------
# ðŸ“Œ CARREGA .ENV
# ---------------------------------------------------------------------
if ENV_PATH.exists():
    load_dotenv(dotenv_path=ENV_PATH)


# ---------------------------------------------------------------------
# ðŸ“Œ FUNÃ‡ÃƒO DE PARSE DO DATABASE_URL
# ---------------------------------------------------------------------
def build_database_config(database_url: str) -> dict:
    parsed = urlparse(database_url)
    django_time_zone = os.getenv(
        "DJANGO_TIME_ZONE",
        os.getenv("TIME_ZONE", "America/Sao_Paulo"),
    )

    if parsed.scheme not in {"postgres", "postgresql"}:
        raise RuntimeError("DATABASE_URL do Django Admin deve apontar para PostgreSQL")

    return {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": unquote(parsed.path.lstrip("/")),
        "USER": unquote(parsed.username or ""),
        "PASSWORD": unquote(parsed.password or ""),
        "HOST": parsed.hostname or "localhost",
        "PORT": str(parsed.port or 5432),
        "OPTIONS": {
            "options": (
                "-c search_path="
                f"{os.getenv('DB_DJANGO_SCHEMA', 'django')},"
                f"{os.getenv('DB_OPERATIONS_SCHEMA', 'portal_industria')},"
                "public "
                f"-c timezone={django_time_zone}"
            )
        },
    }


# ---------------------------------------------------------------------
# ðŸ“Œ CONFIGURAÃ‡Ã•ES GERAIS
# ---------------------------------------------------------------------
SECRET_KEY = os.getenv(
    "DJANGO_SECRET_KEY",
    "dev-only-django-admin-secret-key-change-in-production",
)

DEBUG = os.getenv("DJANGO_DEBUG", "true").lower() == "true"

ALLOWED_HOSTS = [
    host.strip()
    for host in os.getenv("DJANGO_ALLOWED_HOSTS", "127.0.0.1,localhost").split(",")
    if host.strip()
]

CSRF_TRUSTED_ORIGINS = [
    origin.strip()
    for origin in os.getenv("DJANGO_CSRF_TRUSTED_ORIGINS", "https://localhost:8443").split(",")
    if origin.strip()
]

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST = True


# ---------------------------------------------------------------------
# ðŸ“Œ APPS INSTALADOS
# ---------------------------------------------------------------------
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "backend.app.modules.audit.apps.AuditConfig",
    "backend.app.modules.backoffice.apps.BackofficeModuleConfig",
    "backend.app.modules.printers.machines.apps.PrinterMachinesConfig",
]


# ---------------------------------------------------------------------
# PAINEL ADMINISTRATIVO SEM OWNERSHIP DO SCHEMA OPERACIONAL
# ---------------------------------------------------------------------
MIGRATION_MODULES = {
    "audit": None,
    "portal_backoffice": None,
    "printer_machines": None,
}


# ---------------------------------------------------------------------
# ðŸ“Œ MIDDLEWARE
# ---------------------------------------------------------------------
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]


# ---------------------------------------------------------------------
# ðŸ“Œ URLS / WSGI / ASGI
# ---------------------------------------------------------------------
ROOT_URLCONF = "backend.backoffice.urls"
WSGI_APPLICATION = "backend.backoffice.wsgi.application"
ASGI_APPLICATION = "backend.backoffice.asgi.application"


# ---------------------------------------------------------------------
# ðŸ“Œ TEMPLATES
# ---------------------------------------------------------------------
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]


# ---------------------------------------------------------------------
# ðŸ“Œ BANCO DE DADOS
# ---------------------------------------------------------------------
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL nÃ£o encontrada para o Django Admin")

DATABASES = {
    "default": build_database_config(DATABASE_URL)
}


# ---------------------------------------------------------------------
# ðŸ“Œ I18N / TZ
# ---------------------------------------------------------------------
LANGUAGE_CODE = "pt-br"
TIME_ZONE = os.getenv(
    "DJANGO_TIME_ZONE",
    os.getenv("TIME_ZONE", "America/Sao_Paulo"),
)
USE_I18N = True
USE_TZ = False


# ---------------------------------------------------------------------
# ðŸ“Œ STATIC
# ---------------------------------------------------------------------
STATIC_URL = "/static/"
STATIC_ROOT = BACKEND_DIR / "staticfiles"


# ---------------------------------------------------------------------
# ðŸ“Œ DEFAULTS
# ---------------------------------------------------------------------
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

