from unittest import TestCase

from backend.app.modules.audit.orm import Log


class LogTranslationTest(TestCase):
    def test_log_traduz_tipo_de_login(self):
        log = Log(
            tipo="login_success",
            message="Login realizado com sucesso.",
            valor_novo="usuario=Analista_Dev; sucesso=True",
        )

        self.assertEqual(log.tipo, "Login realizado")
        self.assertEqual(log.message, "Login realizado com sucesso.")
        self.assertEqual(log.valor_novo, "usuario=Analista_Dev; sucesso=sim")

    def test_log_de_acesso_negado_traduz_booleano(self):
        log = Log(
            tipo="access_denied",
            message="Acesso negado.",
            valor_novo="usuario=gestor; sucesso=False",
        )

        self.assertEqual(log.tipo, "Acesso negado")
        self.assertEqual(log.valor_novo, "usuario=gestor; sucesso=nao")

