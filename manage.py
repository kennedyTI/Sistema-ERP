"""
Arquivo: manage.py

DescriÃ§Ã£o:
Ponto de entrada do Django Admin.

Responsabilidades:
- Expor comandos do Django
- Permitir migrate, createsuperuser e runserver
- Manter o admin separado do motor FastAPI
"""

import os
import sys


def main():
    """
    Executa comandos administrativos do Django.
    """
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.backoffice.settings")

    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()

