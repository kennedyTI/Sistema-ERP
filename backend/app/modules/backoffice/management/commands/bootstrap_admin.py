"""
Arquivo: backend/backoffice/management/commands/bootstrap_admin.py

Descrição:
Comando auxiliar para criação de superusuário via variáveis de ambiente.

Responsabilidades:
- Facilitar bootstrap local
- Facilitar futura automação no Docker
- Evitar criação manual repetitiva em ambientes novos
"""

import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Cria um superusuário a partir de variáveis de ambiente"

    def handle(self, *args, **options):
        username = os.getenv("DJANGO_SUPERUSER_USERNAME")
        password = os.getenv("DJANGO_SUPERUSER_PASSWORD")
        email = os.getenv("DJANGO_SUPERUSER_EMAIL", "")

        if not username or not password:
            raise CommandError(
                "Defina DJANGO_SUPERUSER_USERNAME e DJANGO_SUPERUSER_PASSWORD"
            )

        user_model = get_user_model()

        if user_model.objects.filter(username=username).exists():
            self.stdout.write(self.style.WARNING("Superusuário já existe"))
            return

        user_model.objects.create_superuser(
            username=username,
            email=email,
            password=password,
        )

        self.stdout.write(self.style.SUCCESS("Superusuário criado com sucesso"))
