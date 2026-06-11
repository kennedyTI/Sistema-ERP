"""
Arquivo: backend/backoffice/asgi.py

Descrição:
ASGI do Django Admin.
"""

import os

from django.core.asgi import get_asgi_application


os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.backoffice.settings")

application = get_asgi_application()


