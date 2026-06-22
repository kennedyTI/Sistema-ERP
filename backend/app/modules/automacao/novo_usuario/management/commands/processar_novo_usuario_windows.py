"""Processa e-mails de admissao e cria usuarios Windows/AD."""

from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q

from backend.app.core.timezone import now_sao_paulo
from backend.app.modules.automacao.novo_usuario.config import (
    NovoUsuarioAutomationSettings,
    get_novo_usuario_settings,
)
from backend.app.modules.automacao.novo_usuario.models import (
    AutomacaoNovoUsuarioWindows,
)
from backend.app.modules.automacao.novo_usuario.services.ad_user_service import (
    ActiveDirectoryError,
    PowerShellADUserService,
    build_ad_user_payload,
)
from backend.app.modules.automacao.novo_usuario.services.admission_email_parser import (
    AdmissionData,
    parse_admission_email_body,
    subject_matches_prefix,
)
from backend.app.modules.automacao.novo_usuario.services.credentials_service import (
    CredentialConfigurationError,
    NovoUsuarioCredentials,
    load_credentials,
)
from backend.app.modules.automacao.novo_usuario.services.deduplication import (
    build_deduplication_filter,
)
from backend.app.modules.automacao.novo_usuario.services.login_generator import (
    generate_login_options,
)
from backend.app.modules.automacao.novo_usuario.services.pop3_email_reader import (
    POP3EmailReader,
    POP3EmailRecord,
)
from backend.app.modules.automacao.novo_usuario.services.smtps_email_sender import (
    SMTPSEmailSender,
)


def email_already_processed(uidl: str | None, message_id: str | None) -> bool:
    filters = build_deduplication_filter(uidl, message_id)
    if filters is None:
        return False
    query = Q()
    for field_name, value in filters:
        query |= Q(**{field_name: value})
    return AutomacaoNovoUsuarioWindows.objects.filter(query).exists()


class Command(BaseCommand):
    help = "Processa admissoes por e-mail e cria usuarios Windows no Active Directory."

    def handle(self, *args, **options):  # noqa: ANN002, ANN003, ARG002
        self._info("Iniciando automacao de novo usuario Windows")
        settings = get_novo_usuario_settings()
        self._info(
            "Modo DRY_RUN ativo" if settings.dry_run else "Modo real ativo"
        )

        try:
            credentials = load_credentials(settings)
        except CredentialConfigurationError as exc:
            raise CommandError(str(exc)) from exc

        self._info("Conectando ao POP3")
        reader = POP3EmailReader(settings)
        try:
            emails = reader.fetch_recent(credentials)
        except Exception as exc:
            raise CommandError(f"Falha ao ler e-mails via POP3: {exc}") from exc

        self._info(
            f"Buscando e-mails dos ultimos {settings.email_lookback_minutes} minutos"
        )

        processed = 0
        ignored = 0
        for email_record in emails:
            if not subject_matches_prefix(
                email_record.subject,
                settings.email_subject_prefix,
            ):
                ignored += 1
                continue

            self._info(f"E-mail encontrado: {email_record.subject}")
            if email_already_processed(
                email_record.uidl,
                email_record.message_id,
            ):
                self._info("E-mail ignorado por UIDL/Message-ID ja processado")
                ignored += 1
                continue

            record = self._create_initial_record(
                email_record,
                settings,
                credentials,
            )
            self._process_record(record, email_record, settings, credentials)
            processed += 1

        self._ok(
            f"Processo concluido. Processados: {processed}. Ignorados: {ignored}."
        )

    def _process_record(
        self,
        record: AutomacaoNovoUsuarioWindows,
        email_record: POP3EmailRecord,
        settings: NovoUsuarioAutomationSettings,
        credentials: NovoUsuarioCredentials,
    ) -> None:
        admission: AdmissionData | None = None
        try:
            self._set_status(record, AutomacaoNovoUsuarioWindows.STATUS_PROCESSANDO)
            self._info("Extraindo dados do e-mail")
            admission = parse_admission_email_body(email_record.body)
            self._fill_admission_fields(record, admission)

            self._info("Gerando login")
            login_options = generate_login_options(admission.nome_completo)
            record.login_tentativa_primaria = login_options.primary
            record.login_tentativa_secundaria = login_options.secondary
            record.atualizado_em = now_sao_paulo()
            record.save(
                update_fields=[
                    "login_tentativa_primaria",
                    "login_tentativa_secundaria",
                    "atualizado_em",
                ]
            )

            selected_login = login_options.primary
            alternative_used = False

            if settings.dry_run:
                record.login_gerado = selected_login
                record.login_alternativo_usado = alternative_used
                record.dominio_ad = settings.ad_domain
                record.ou_destino = settings.ad_ou
                record.escritorio = settings.ad_office
                record.empresa = settings.ad_company
                record.grupos_aplicados = "\n".join(settings.ad_groups)
                record.resultado_powershell = (
                    "DRY_RUN: usuario nao criado. "
                    f"Login planejado: {selected_login}. "
                    f"OU: {settings.ad_ou}. "
                    f"Grupos: {', '.join(settings.ad_groups)}."
                )
                record.status = AutomacaoNovoUsuarioWindows.STATUS_DRY_RUN
                record.processado_em = now_sao_paulo()
                record.atualizado_em = now_sao_paulo()
                record.save()
                self._info("DRY_RUN: verificacao/criacao no AD nao executada")
                self._info(f"DRY_RUN: usuario seria criado na OU {settings.ad_ou}")
                self._info(
                    "DRY_RUN: grupos que seriam aplicados: "
                    + ", ".join(settings.ad_groups)
                )
                self._info("DRY_RUN: envio de e-mail real nao executado")
                self._ok("Processo concluido em dry run")
                return

            ad_service = PowerShellADUserService(settings)
            self._info("Verificando modulo ActiveDirectory")
            ad_service.assert_active_directory_module_available()

            self._info("Verificando login no AD")
            if ad_service.login_exists(login_options.primary):
                if not login_options.secondary:
                    raise ActiveDirectoryError(
                        "Login primario ja existe e nao ha tentativa secundaria valida."
                    )
                if ad_service.login_exists(login_options.secondary):
                    raise ActiveDirectoryError(
                        "Login primario e secundario ja existem no AD."
                    )
                selected_login = login_options.secondary
                alternative_used = True

            payload = build_ad_user_payload(admission, selected_login, settings)
            self._info("Criando usuario no AD")
            self._info("Aplicando senha temporaria e troca obrigatoria no proximo logon")
            self._info("Aplicando grupos")
            result = ad_service.create_user(
                payload,
                temporary_password=credentials.temporary_password,
            )

            record.login_gerado = selected_login
            record.login_alternativo_usado = alternative_used
            record.dominio_ad = settings.ad_domain
            record.ou_destino = settings.ad_ou
            record.escritorio = settings.ad_office
            record.empresa = settings.ad_company
            record.grupos_aplicados = "\n".join(settings.ad_groups)
            record.resultado_powershell = result.output
            record.status = AutomacaoNovoUsuarioWindows.STATUS_CONCLUIDO
            record.processado_em = now_sao_paulo()
            record.atualizado_em = now_sao_paulo()
            record.save()

            self._info("Enviando resposta ao solicitante")
            self._send_success_response(
                record,
                admission,
                settings,
                credentials,
            )
            self._ok("Processo concluido")
        except Exception as exc:
            self._error(str(exc))
            self._register_failure(
                record,
                admission,
                settings,
                credentials,
                str(exc),
            )

    def _create_initial_record(
        self,
        email_record: POP3EmailRecord,
        settings: NovoUsuarioAutomationSettings,
        credentials: NovoUsuarioCredentials,
    ) -> AutomacaoNovoUsuarioWindows:
        now = now_sao_paulo()
        return AutomacaoNovoUsuarioWindows.objects.create(
            uidl_email=email_record.uidl,
            message_id_email=email_record.message_id,
            remetente=email_record.sender,
            destinatario=email_record.recipient,
            assunto=email_record.subject,
            data_email=email_record.date,
            corpo_email=email_record.body,
            senha_temporaria_mascarada=credentials.temporary_password_masked,
            status=AutomacaoNovoUsuarioWindows.STATUS_RECEBIDO,
            dry_run=settings.dry_run,
            recebido_em=now,
            criado_em=now,
            atualizado_em=now,
        )

    def _fill_admission_fields(
        self,
        record: AutomacaoNovoUsuarioWindows,
        admission: AdmissionData,
    ) -> None:
        record.pn = admission.pn
        record.nome_completo = admission.nome_completo
        record.cargo = admission.cargo
        record.unid_org = admission.unid_org
        record.data_admissao = admission.data_admissao
        record.atualizado_em = now_sao_paulo()
        record.save(
            update_fields=[
                "pn",
                "nome_completo",
                "cargo",
                "unid_org",
                "data_admissao",
                "atualizado_em",
            ]
        )

    def _set_status(
        self,
        record: AutomacaoNovoUsuarioWindows,
        status: str,
    ) -> None:
        record.status = status
        record.atualizado_em = now_sao_paulo()
        record.save(update_fields=["status", "atualizado_em"])

    def _send_success_response(
        self,
        record: AutomacaoNovoUsuarioWindows,
        admission: AdmissionData,
        settings: NovoUsuarioAutomationSettings,
        credentials: NovoUsuarioCredentials,
    ) -> None:
        body = _success_body(record, admission, settings, credentials)
        subject = f"Usuário Windows criado - {admission.nome_completo}"
        sender = SMTPSEmailSender(settings)
        sender.send_text(
            credentials=credentials,
            to_email=record.remetente,
            subject=subject,
            body=body,
        )
        record.respondido_email = True
        record.email_resposta_enviado_para = record.remetente
        record.respondido_em = now_sao_paulo()
        record.status = AutomacaoNovoUsuarioWindows.STATUS_RESPONDIDO
        record.atualizado_em = now_sao_paulo()
        record.save(
            update_fields=[
                "respondido_email",
                "email_resposta_enviado_para",
                "respondido_em",
                "status",
                "atualizado_em",
            ]
        )

    def _register_failure(
        self,
        record: AutomacaoNovoUsuarioWindows,
        admission: AdmissionData | None,
        settings: NovoUsuarioAutomationSettings,
        credentials: NovoUsuarioCredentials,
        error: str,
    ) -> None:
        record.status = AutomacaoNovoUsuarioWindows.STATUS_FALHOU
        record.erro = error
        record.processado_em = now_sao_paulo()
        record.atualizado_em = now_sao_paulo()
        record.save(
            update_fields=[
                "status",
                "erro",
                "processado_em",
                "atualizado_em",
            ]
        )

        self._info(f"Enviando aviso para {settings.failure_email}")
        if settings.dry_run:
            self._info("DRY_RUN: aviso de falha nao enviado por e-mail")
            return

        sender = SMTPSEmailSender(settings)
        try:
            sender.send_text(
                credentials=credentials,
                to_email=settings.failure_email,
                subject=(
                    "Falha na automação de novo usuário Windows - "
                    f"{record.nome_completo or 'NOME NAO IDENTIFICADO'}"
                ),
                body=_failure_body(record, admission, settings, error),
            )
        except Exception as exc:
            record.erro = f"{error}\nFalha ao enviar aviso de falha: {exc}"
            record.atualizado_em = now_sao_paulo()
            record.save(update_fields=["erro", "atualizado_em"])
            self._error(f"Falha ao enviar aviso de falha: {exc}")
            return
        record.respondido_email = True
        record.email_resposta_enviado_para = settings.failure_email
        record.respondido_em = now_sao_paulo()
        record.atualizado_em = now_sao_paulo()
        record.save(
            update_fields=[
                "respondido_email",
                "email_resposta_enviado_para",
                "respondido_em",
                "atualizado_em",
            ]
        )

    def _info(self, message: str) -> None:
        self.stdout.write(f"[INFO] {message}")

    def _ok(self, message: str) -> None:
        self.stdout.write(f"[OK] {message}")

    def _error(self, message: str) -> None:
        self.stderr.write(f"[ERRO] {message}")


def _success_body(
    record: AutomacaoNovoUsuarioWindows,
    admission: AdmissionData,
    settings: NovoUsuarioAutomationSettings,
    credentials: NovoUsuarioCredentials,
) -> str:
    groups = "\n".join(f"- {group}" for group in settings.ad_groups)
    return f"""Solicitação processada com sucesso.

Nome: {admission.nome_completo}
PN: {admission.pn}
Login: {record.login_gerado}
Senha temporária: {credentials.temporary_password}

Atenção:
Esta é uma senha temporária. O usuário deverá alterar a senha no primeiro logon.

Grupos aplicados:
{groups}

Escritório: {settings.ad_office}
Cargo: {admission.cargo}
Departamento: {admission.unid_org}

---
Mensagem enviada automaticamente pelo módulo de Automação de Novo Usuário Windows.
Sistema ERP - Automação de TI
"""


def _failure_body(
    record: AutomacaoNovoUsuarioWindows,
    admission: AdmissionData | None,
    settings: NovoUsuarioAutomationSettings,
    error: str,
) -> str:
    return f"""A automação tentou processar uma solicitação de criação de usuário, mas não concluiu a execução.

Dados da solicitação:
PN: {record.pn or (admission.pn if admission else '')}
Nome: {record.nome_completo or (admission.nome_completo if admission else '')}
Cargo: {record.cargo or (admission.cargo if admission else '')}
Unid. Org.: {record.unid_org or (admission.unid_org if admission else '')}
Data admissão: {admission.data_admissao_formatada if admission else ''}
Remetente: {record.remetente or ''}
Assunto: {record.assunto or ''}

Motivo da falha:
{error}

Ação necessária:
Verificar manualmente no Active Directory.

---
Mensagem enviada automaticamente pelo módulo de Automação de Novo Usuário Windows.
Sistema ERP - Automação de TI
"""
