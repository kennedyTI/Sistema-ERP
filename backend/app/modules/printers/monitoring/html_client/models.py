"""Objetos de transferencia do cliente HTML seguro."""

from dataclasses import dataclass


@dataclass(frozen=True)
class HtmlAccessConfig:
    modelo_id: int
    tipo_autenticacao: str
    senha: str | None
    usuario: str | None = None
    caminho_status: str | None = None
    caminho_informacoes: str | None = None
    caminho_login: str | None = None
    timeout_segundos: int = 5
    protocolo_preferencial: str = "auto"
    validar_ssl: bool = False


@dataclass(frozen=True)
class HtmlClientResponse:
    sucesso: bool
    status_code: int | None
    url_sanitizada: str | None
    conteudo_html: str | None
    erro_codigo: str | None
    erro_detalhe_sanitizado: str | None
    protocolo_usado: str | None
    tipo_autenticacao: str

