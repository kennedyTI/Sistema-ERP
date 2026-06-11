"""
Arquivo: backend/backoffice/urls.py

Descrição:
Mapeamento de rotas do Django Admin.
"""

import os

from django.contrib import admin
from django.urls import path


# ---------------------------------------------------------------------
# 📌 CAMINHO DO ADMIN
# ---------------------------------------------------------------------
# O prefixo configurável permite publicar o Admin atrás do mesmo proxy sem
# acoplar as URLs internas do Django à porta exposta no ambiente local.
ADMIN_PATH = os.getenv("DJANGO_ADMIN_PATH", "admin/").strip("/")

urlpatterns = [
    path(f"{ADMIN_PATH}/", admin.site.urls),
]

