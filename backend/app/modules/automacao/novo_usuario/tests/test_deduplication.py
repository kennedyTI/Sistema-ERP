from unittest import TestCase

from backend.app.modules.automacao.novo_usuario.services.deduplication import (
    build_deduplication_filter,
)


class DeduplicationTest(TestCase):
    def test_builds_filter_for_uidl_and_message_id(self):
        query = build_deduplication_filter("uidl-1", "<message@example>")

        self.assertIsNotNone(query)
        self.assertEqual(
            {field_name for field_name, _value in query},
            {"uidl_email", "message_id_email"},
        )

    def test_returns_none_without_identifiers(self):
        self.assertIsNone(build_deduplication_filter(None, None))
