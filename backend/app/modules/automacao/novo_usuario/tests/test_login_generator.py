from unittest import TestCase

from backend.app.modules.automacao.novo_usuario.services.login_generator import (
    generate_login_options,
    normalize_login_part,
)


class LoginGeneratorTest(TestCase):
    def test_primary_login_uses_first_name_and_last_surname(self):
        options = generate_login_options("PIERRE MENDES DE SOUSA")

        self.assertEqual(options.primary, "pierre.sousa")

    def test_secondary_login_uses_penultimate_surname(self):
        options = generate_login_options("PIERRE MENDES DE SOUSA")

        self.assertEqual(options.secondary, "pierre.mendes")

    def test_particles_are_ignored_when_selecting_surnames(self):
        options = generate_login_options("MARIA DA CONCEIÇÃO DOS SANTOS")

        self.assertEqual(options.primary, "maria.santos")
        self.assertEqual(options.secondary, "maria.conceicao")

    def test_login_part_removes_accents_and_special_characters(self):
        self.assertEqual(normalize_login_part("João-Pedro"), "joaopedro")
