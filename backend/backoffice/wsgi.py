"""
Arquivo: backend/backoffice/wsgi.py

DescriÃ§Ã£o:
WSGI do Django Admin.
"""

import os

from django.core.wsgi import get_wsgi_application


os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.backoffice.settings")

application = get_wsgi_application()


