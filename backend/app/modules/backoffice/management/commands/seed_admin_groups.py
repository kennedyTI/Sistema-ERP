"""
Cria/atualiza grupos oficiais do Portal industria v2 base.
"""

from django.core.management.base import BaseCommand

from backend.app.modules.backoffice.groups import GROUPS, OLD_GROUP_RENAMES
from backend.app.modules.backoffice.services import sync_official_groups


class Command(BaseCommand):
    help = "Cria/atualiza grupos e permissoes oficiais do Django Admin"

    def handle(self, *args, **options):
        for message in sync_official_groups():
            self.stdout.write(self.style.SUCCESS(message))
