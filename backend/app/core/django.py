"""
Bootstrap do Django usado pelo FastAPI para autenticar via Django Auth.
"""

from __future__ import annotations

import os

from django.apps import apps


def ensure_django_ready() -> None:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.backoffice.settings")
    if not apps.ready:
        import django

        django.setup()
