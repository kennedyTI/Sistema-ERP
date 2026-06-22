"""Envio SMTPS das respostas da automacao."""

from __future__ import annotations

import smtplib
from email.message import EmailMessage

from backend.app.modules.automacao.novo_usuario.config import (
    NovoUsuarioAutomationSettings,
)
from backend.app.modules.automacao.novo_usuario.services.credentials_service import (
    NovoUsuarioCredentials,
)


class SMTPSEmailSender:
    def __init__(self, settings: NovoUsuarioAutomationSettings):
        self.settings = settings

    def send_text(
        self,
        *,
        credentials: NovoUsuarioCredentials,
        to_email: str,
        subject: str,
        body: str,
    ) -> None:
        if not self.settings.smtp_ssl:
            raise RuntimeError("A automacao foi configurada para exigir SMTPS com SSL.")

        message = EmailMessage()
        message["From"] = credentials.email
        message["To"] = to_email
        message["Subject"] = subject
        message.set_content(body)

        with smtplib.SMTP_SSL(self.settings.smtp_host, self.settings.smtp_port) as client:
            client.login(credentials.email, credentials.email_password)
            client.send_message(message)
