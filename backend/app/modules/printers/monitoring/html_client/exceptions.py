"""Excecoes controladas do cliente HTML de impressoras."""


class HtmlClientError(RuntimeError):
    def __init__(self, code: str, detail: str):
        super().__init__(detail)
        self.code = code
        self.detail = detail


class UnsupportedAuthenticationError(HtmlClientError):
    def __init__(self):
        super().__init__(
            "autenticacao_nao_suportada_nesta_etapa",
            "Autenticacao form/cookie sera implementada em etapa futura.",
        )

