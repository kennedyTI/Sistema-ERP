"""
Arquivo: backend/backoffice/urls.py

DescriÃ§Ã£o:
Mapeamento de rotas do Django Admin.
"""

import os

from django.contrib import admin
from django.urls import path


# ---------------------------------------------------------------------
# ðŸ“Œ CAMINHO DO ADMIN
# ---------------------------------------------------------------------
ADMIN_PATH = os.getenv("DJANGO_ADMIN_PATH", "admin/").strip("/")

urlpatterns = [
    path(f"{ADMIN_PATH}/", admin.site.urls),
]

