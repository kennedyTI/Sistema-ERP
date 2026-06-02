from unittest import TestCase
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.app.core.security import create_access_token
from backend.app.core.database import get_db
from backend.app.main import app
from backend.app.modules.auth.permissions import portal_permissions_for_groups
from backend.app.modules.auth.schemas import PortalPermissions
from backend.tests.auth_helpers import auth_headers, make_user


class FakeDb:
    def __init__(self):
        self.added = []
        self.commits = 0
        self.rollbacks = 0

    def add(self, obj):
        self.added.append(obj)

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


class PortalAuthApiTest(TestCase):
    def setUp(self):
        self.db = FakeDb()

        def override_db():
            yield self.db

        app.dependency_overrides[get_db] = override_db
        self.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.clear()

    def test_login_valido_retorna_jwt_v2(self):
        user = make_user(username="tecnico", admin=True)

        with patch("backend.app.modules.auth.api.authenticate_django_user", return_value=user):
            response = self.client.post(
                "/api/v2/auth/login",
                json={"username": "tecnico", "password": "senha-correta"},
            )

        payload = response.json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["token_type"], "bearer")
        self.assertTrue(payload["access_token"])
        self.assertEqual(payload["user"]["username"], "tecnico")
        self.assertTrue(payload["user"]["permissions"]["can_access_admin"])

    def test_auth_v1_permanece_temporariamente_compativel(self):
        user = make_user(username="tecnico", admin=True)

        with patch("backend.app.modules.auth.api.authenticate_django_user", return_value=user):
            response = self.client.post(
                "/api/v1/auth/login",
                json={"username": "tecnico", "password": "senha-correta"},
            )

        self.assertEqual(response.status_code, 200)

    def test_login_senha_invalida_retorna_erro_generico(self):
        with patch("backend.app.modules.auth.api.authenticate_django_user", return_value=None):
            response = self.client.post(
                "/api/v2/auth/login",
                json={"username": "qualquer", "password": "senha-secreta"},
            )

        payload = response.json()
        self.assertEqual(response.status_code, 401)
        self.assertFalse(payload["success"])
        self.assertEqual(payload["message"], "Usuario ou senha invalidos.")
        self.assertNotIn("senha-secreta", str(self.db.added))

    def test_auth_me_retorna_usuario_do_token(self):
        response = self.client.get("/api/v2/auth/me", headers=auth_headers(username="gestor"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["username"], "gestor")

    def test_token_invalido_retorna_401(self):
        response = self.client.get("/api/v2/auth/me", headers={"Authorization": "Bearer invalido"})

        self.assertEqual(response.status_code, 401)

    def test_token_expirado_retorna_401(self):
        token = create_access_token(make_user(), expires_minutes=1, issued_at=0)
        response = self.client.get("/api/v2/auth/me", headers={"Authorization": f"Bearer {token}"})

        self.assertEqual(response.status_code, 401)

    def test_logout_registra_evento(self):
        response = self.client.post("/api/v2/auth/logout", headers=auth_headers(username="tecnico"))

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["success"])
        self.assertGreaterEqual(len(self.db.added), 2)


class PortalPermissionsTest(TestCase):
    def test_equipe_tecnica_acessa_inicio_e_admin(self):
        permissions = portal_permissions_for_groups(["Equipe T\u00e9cnica"])

        self.assertTrue(permissions.can_access_portal)
        self.assertTrue(permissions.can_access_admin)

    def test_gestor_acessa_inicio_sem_admin(self):
        permissions = portal_permissions_for_groups(["Gestor"])

        self.assertTrue(permissions.can_access_portal)
        self.assertFalse(permissions.can_access_admin)

    def test_operador_acessa_inicio_sem_admin(self):
        permissions = portal_permissions_for_groups(["Operador"])

        self.assertTrue(permissions.can_access_portal)
        self.assertFalse(permissions.can_access_admin)

    def test_integracao_protheus_nao_acessa_portal_visual(self):
        permissions = portal_permissions_for_groups(["Integra\u00e7\u00e3o Protheus"])

        self.assertEqual(permissions, PortalPermissions())

