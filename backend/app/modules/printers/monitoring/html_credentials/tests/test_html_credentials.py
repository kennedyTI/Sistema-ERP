import os
from pathlib import Path
from unittest import TestCase

import django
from cryptography.fernet import Fernet
from django.apps import apps
from django.contrib.admin.sites import AdminSite
from sqlalchemy import CheckConstraint, create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.backoffice.settings")
if not apps.ready:
    django.setup()

from backend.app.modules.printers.machines.models import PrinterModel  # noqa: E402
from backend.app.modules.printers.monitoring.html_credentials.admin import (  # noqa: E402
    PrinterCollectionCredentialAdmin,
    credential_audit_snapshot,
)
from backend.app.modules.printers.monitoring.html_credentials.crypto import (  # noqa: E402
    CredentialCryptoError,
    decrypt_password,
    encrypt_password,
)
from backend.app.modules.printers.monitoring.html_credentials.django_models import (  # noqa: E402
    PrinterCollectionCredentialAdminModel,
)
from backend.app.modules.printers.monitoring.html_credentials.models import (  # noqa: E402
    ALLOWED_AUTH_TYPES,
    PrinterCollectionCredential,
)
from backend.app.modules.printers.monitoring.html_credentials.services import (  # noqa: E402
    credential_metadata,
    create_collection_credential,
    get_active_credential_for_model,
    get_credential_metadata_for_model,
)


MIGRATION_PATH = Path(
    "backend/app/migrations/versions/20260618_printer_html_credentials.py"
)


class PermissionUserStub:
    is_active = True
    is_staff = True
    is_authenticated = True

    def __init__(self, permissions=(), *, is_superuser=False):
        self.permissions = set(permissions)
        self.is_superuser = is_superuser

    def has_perm(self, permission):
        return permission in self.permissions

    def get_username(self):
        return "usuario_teste"


class RequestStub:
    GET = {}

    def __init__(self, user):
        self.user = user


class HtmlCredentialModelTest(TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        PrinterModel.__table__.create(self.engine)
        PrinterCollectionCredential.__table__.create(self.engine)
        self.db = sessionmaker(bind=self.engine)()
        self.model = PrinterModel(manufacturer="Fabricante", name="Modelo X")
        self.db.add(self.model)
        self.db.commit()

    def tearDown(self):
        self.db.close()

    def _credential(self, *, active=True, auth_type="basic", name="Credencial"):
        return PrinterCollectionCredential(
            nome=name,
            tipo_autenticacao=auth_type,
            modelo_id=self.model.id,
            usuario="usuario_teste",
            senha_criptografada="token-seguro",
            ativo=active,
        )

    def test_migration_cria_tabela_campos_constraints_e_indice_parcial(self):
        content = MIGRATION_PATH.read_text(encoding="utf-8")

        self.assertIn('down_revision = "20260617_alerts_persistence"', content)
        self.assertIn('"credenciais_coleta_impressoras"', content)
        self.assertIn('"modelo_id"', content)
        self.assertIn("fk_credenciais_coleta_impressoras_modelo_id", content)
        self.assertIn("uq_credenciais_coleta_impressoras_modelo_ativo", content)
        self.assertIn("postgresql_where=sa.text(\"ativo IS true\")", content)

    def test_modelo_define_apenas_escopo_por_modelo(self):
        columns = set(PrinterCollectionCredential.__table__.columns.keys())

        self.assertEqual(
            columns,
            {
                "id",
                "nome",
                "descricao",
                "tipo_autenticacao",
                "modelo_id",
                "usuario",
                "senha_criptografada",
                "ativo",
                "criado_em",
                "atualizado_em",
            },
        )
        self.assertFalse(PrinterCollectionCredential.__table__.c.modelo_id.nullable)
        self.assertNotIn("maquina_id", columns)
        self.assertNotIn("fabricante", columns)
        self.assertNotIn("escopo", columns)

    def test_tipo_autenticacao_controlado(self):
        check_text = " ".join(
            str(constraint.sqltext)
            for constraint in PrinterCollectionCredential.__table__.constraints
            if isinstance(constraint, CheckConstraint)
        )

        for auth_type in ALLOWED_AUTH_TYPES:
            self.assertIn(auth_type, check_text)

    def test_tipos_validos_sao_aceitos(self):
        for index, auth_type in enumerate(ALLOWED_AUTH_TYPES, start=1):
            model = PrinterModel(manufacturer="Fabricante", name=f"Modelo {index}")
            self.db.add(model)
            self.db.flush()
            self.db.add(
                PrinterCollectionCredential(
                    nome=f"Credencial {auth_type}",
                    tipo_autenticacao=auth_type,
                    modelo_id=model.id,
                    usuario="usuario_teste",
                    senha_criptografada="token-seguro",
                )
            )

        self.db.commit()
        self.assertEqual(self.db.query(PrinterCollectionCredential).count(), 4)

    def test_tipo_invalido_e_rejeitado(self):
        self.db.add(self._credential(auth_type="oauth"))

        with self.assertRaises(IntegrityError):
            self.db.commit()

    def test_apenas_uma_credencial_ativa_por_modelo(self):
        self.db.add(self._credential(name="Credencial 1"))
        self.db.add(self._credential(name="Credencial 2"))

        with self.assertRaises(IntegrityError):
            self.db.commit()

    def test_credenciais_inativas_duplicadas_sao_permitidas(self):
        self.db.add(self._credential(active=False, name="Inativa 1"))
        self.db.add(self._credential(active=False, name="Inativa 2"))
        self.db.add(self._credential(active=True, name="Ativa"))

        self.db.commit()
        self.assertEqual(self.db.query(PrinterCollectionCredential).count(), 3)


class HtmlCredentialCryptoTest(TestCase):
    def setUp(self):
        self.secret_key = Fernet.generate_key().decode("utf-8")

    def test_criptografa_e_descriptografa_senha(self):
        encrypted = encrypt_password("senha-ficticia", secret_key=self.secret_key)

        self.assertNotEqual(encrypted, "senha-ficticia")
        self.assertNotIn("senha-ficticia", encrypted)
        self.assertEqual(
            decrypt_password(encrypted, secret_key=self.secret_key),
            "senha-ficticia",
        )

    def test_operacao_sensivel_falha_sem_chave(self):
        with self.assertRaises(CredentialCryptoError):
            encrypt_password("senha-ficticia", secret_key="")


class HtmlCredentialServiceTest(TestCase):
    def setUp(self):
        self.previous_key = os.environ.get("PRINTER_CREDENTIALS_SECRET_KEY")
        os.environ["PRINTER_CREDENTIALS_SECRET_KEY"] = Fernet.generate_key().decode("utf-8")
        engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        PrinterModel.__table__.create(engine)
        PrinterCollectionCredential.__table__.create(engine)
        self.db = sessionmaker(bind=engine)()
        self.model = PrinterModel(manufacturer="Fabricante", name="Modelo Y")
        self.other_model = PrinterModel(manufacturer="Fabricante", name="Modelo Z")
        self.db.add_all([self.model, self.other_model])
        self.db.commit()

    def tearDown(self):
        if self.previous_key is None:
            os.environ.pop("PRINTER_CREDENTIALS_SECRET_KEY", None)
        else:
            os.environ["PRINTER_CREDENTIALS_SECRET_KEY"] = self.previous_key
        self.db.close()

    def test_service_cria_credencial_sem_expor_senha_em_metadados(self):
        credential = create_collection_credential(
            self.db,
            nome="Credencial",
            tipo_autenticacao="basic",
            modelo_id=self.model.id,
            usuario="usuario_teste",
            senha="senha-ficticia",
        )
        self.db.commit()

        metadata = credential_metadata(credential)
        self.assertNotIn("senha", metadata)
        self.assertNotIn("senha_criptografada", metadata)
        self.assertNotIn("senha-ficticia", str(metadata))

    def test_service_busca_credencial_ativa_por_modelo(self):
        create_collection_credential(
            self.db,
            nome="Ativa",
            tipo_autenticacao="digest",
            modelo_id=self.model.id,
            usuario="usuario_teste",
            senha="senha-ficticia",
        )
        self.db.commit()

        result = get_active_credential_for_model(self.db, model_id=self.model.id)

        self.assertIsNotNone(result)
        self.assertEqual(result.nome, "Ativa")

    def test_service_ignora_credencial_inativa(self):
        create_collection_credential(
            self.db,
            nome="Inativa",
            tipo_autenticacao="form",
            modelo_id=self.model.id,
            usuario="usuario_teste",
            senha="senha-ficticia",
            ativo=False,
        )
        self.db.commit()

        self.assertIsNone(get_active_credential_for_model(self.db, model_id=self.model.id))

    def test_service_metadados_nao_retorna_segredos(self):
        create_collection_credential(
            self.db,
            nome="Ativa",
            tipo_autenticacao="cookie",
            modelo_id=self.model.id,
            usuario="usuario_teste",
            senha="senha-ficticia",
        )
        self.db.commit()

        metadata = get_credential_metadata_for_model(self.db, model_id=self.model.id)

        self.assertEqual(metadata["tipo_autenticacao"], "cookie")
        self.assertNotIn("senha", metadata)
        self.assertNotIn("senha_criptografada", metadata)


class HtmlCredentialAdminTest(TestCase):
    def setUp(self):
        self.model_admin = PrinterCollectionCredentialAdmin(
            PrinterCollectionCredentialAdminModel,
            AdminSite(),
        )

    def test_admin_expoe_apenas_metadados_seguros_na_lista(self):
        self.assertEqual(
            self.model_admin.list_display,
            (
                "nome",
                "modelo",
                "tipo_autenticacao",
                "usuario",
                "ativo",
                "criado_em",
                "atualizado_em",
            ),
        )
        self.assertNotIn("senha_criptografada", self.model_admin.list_display)
        self.assertNotIn("senha", self.model_admin.list_display)

    def test_admin_nao_exibe_senha_criptografada_no_formulario(self):
        self.assertNotIn("senha_criptografada", self.model_admin.fields)
        self.assertIn("senha_mascarada", self.model_admin.readonly_fields)

        obj = PrinterCollectionCredentialAdminModel(
            nome="Credencial",
            tipo_autenticacao="basic",
            usuario="usuario_teste",
            senha_criptografada="token-encriptado-ficticio",
        )

        masked = self.model_admin.senha_mascarada(obj)
        self.assertNotIn("token-encriptado-ficticio", masked)
        self.assertNotIn("senha-ficticia", masked)

    def test_auditoria_nao_registra_senha_criptografada_completa(self):
        obj = PrinterCollectionCredentialAdminModel(
            nome="Credencial",
            tipo_autenticacao="basic",
            usuario="usuario_teste",
            senha_criptografada="token-encriptado-ficticio",
        )

        snapshot = credential_audit_snapshot(obj)

        self.assertEqual(snapshot["senha_criptografada"], "senha cadastrada")
        self.assertNotIn("token-encriptado-ficticio", str(snapshot))

    def test_superuser_pode_criar_editar_e_desativar_sem_excluir(self):
        request = RequestStub(PermissionUserStub(is_superuser=True))

        self.assertTrue(self.model_admin.has_add_permission(request))
        self.assertTrue(self.model_admin.has_change_permission(request))
        self.assertTrue(self.model_admin.has_view_permission(request))
        self.assertFalse(self.model_admin.has_delete_permission(request))

    def test_equipe_tecnica_consulta_metadados_sem_escrita(self):
        request = RequestStub(
            PermissionUserStub(
                {"printer_machines.view_printercollectioncredentialadminmodel"}
            )
        )

        self.assertTrue(self.model_admin.has_view_permission(request))
        self.assertFalse(self.model_admin.has_add_permission(request))
        self.assertFalse(self.model_admin.has_change_permission(request))
        self.assertFalse(self.model_admin.has_delete_permission(request))
        self.assertNotIn("senha", self.model_admin.get_fields(request))

    def test_operador_nao_acessa_admin_de_credenciais(self):
        request = RequestStub(PermissionUserStub())

        self.assertFalse(self.model_admin.has_view_permission(request))
        self.assertFalse(self.model_admin.has_add_permission(request))
        self.assertFalse(self.model_admin.has_change_permission(request))
        self.assertFalse(self.model_admin.has_delete_permission(request))

    def test_admin_fica_no_grupo_impressoras_com_plural_padronizado(self):
        self.assertEqual(
            PrinterCollectionCredentialAdminModel._meta.app_label,
            "printer_machines",
        )
        self.assertEqual(
            PrinterCollectionCredentialAdminModel._meta.verbose_name_plural,
            "CREDENCIAIS_COLETA_IMPRESSORAS",
        )


class HtmlCredentialScopeTest(TestCase):
    def test_nao_existe_seed_de_credenciais(self):
        scripts_dir = Path("backend/scripts")
        filenames = [path.name for path in scripts_dir.glob("*credential*")]

        self.assertEqual(filenames, [])
