from unittest import TestCase

from backend.app.modules.automacao.novo_usuario.services.admission_email_parser import (
    AdmissionEmailParseError,
    parse_admission_email_body,
    subject_matches_prefix,
)


class AdmissionEmailParserTest(TestCase):
    def test_parse_text_email(self):
        body = """
        PN: 002826
        NOME: PIERRE MENDES DE SOUSA
        CARGO: OFICIAL MANUT-LAM 3
        UNID. ORG.: PROJETO LAMINACAO
        DATA ADMISSÃO: 19/06/2026
        """

        data = parse_admission_email_body(body)

        self.assertEqual(data.pn, "002826")
        self.assertEqual(data.nome_completo, "PIERRE MENDES DE SOUSA")
        self.assertEqual(data.cargo, "OFICIAL MANUT-LAM 3")
        self.assertEqual(data.unid_org, "PROJETO LAMINACAO")
        self.assertEqual(data.data_admissao_formatada, "19/06/2026")

    def test_parse_html_table_email(self):
        body = """
        <table>
          <tr><td>PN:</td><td>002826</td></tr>
          <tr><td>NOME:</td><td>PIERRE MENDES DE SOUSA</td></tr>
          <tr><td>CARGO:</td><td>OFICIAL MANUT-LAM 3</td></tr>
          <tr><td>UNID. ORG.:</td><td>PROJETO LAMINACAO</td></tr>
          <tr><td>DATA ADMISSÃO:</td><td>19/06/2026</td></tr>
        </table>
        """

        data = parse_admission_email_body(body)

        self.assertEqual(data.pn, "002826")
        self.assertEqual(data.nome_completo, "PIERRE MENDES DE SOUSA")
        self.assertEqual(data.unid_org, "PROJETO LAMINACAO")

    def test_missing_required_field_raises_clear_error(self):
        body = """
        PN: 002826
        NOME: PIERRE MENDES DE SOUSA
        DATA ADMISSÃO: 19/06/2026
        """

        with self.assertRaises(AdmissionEmailParseError) as context:
            parse_admission_email_body(body)

        self.assertIn("CARGO", str(context.exception))
        self.assertIn("UNID. ORG.", str(context.exception))

    def test_subject_prefix_is_accent_insensitive(self):
        self.assertTrue(subject_matches_prefix("ADMISSAO - PIERRE", "ADMISSÃO -"))
