from unittest import TestCase
from tempfile import TemporaryDirectory
from pathlib import Path

from backend.app.modules.automacao.novo_usuario.services.credentials_service import (
    load_credentials_from_file,
    mask_secret,
)


class CredentialsServiceTest(TestCase):
    def test_temporary_password_is_masked(self):
        self.assertEqual(mask_secret("Abcde12345"), "**********")

    def test_short_password_is_fully_masked(self):
        self.assertEqual(mask_secret("abc"), "***")

    def test_loader_ignores_unrelated_local_lines(self):
        with TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "Portal RH.url"
            path.write_text(
                """
[automacao_novo_usuario_email]
EMAIL=conta.existente@seudominio.com.br
SENHA=senha_email_teste

[automacao_novo_usuario_windows]
SENHA_TEMPORARIA=senha_windows_teste
IR-C3326I\t/rps/dstatus.cgi?counter=1
IR-C3326I\t/rps/dstatus.cgi?counter=2
""".strip(),
                encoding="utf-8",
            )

            credentials = load_credentials_from_file(path)

        self.assertEqual(credentials.email, "conta.existente@seudominio.com.br")
        self.assertEqual(
            credentials.temporary_password_masked,
            "*" * len("senha_windows_teste"),
        )
