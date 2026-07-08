"""Excecoes controladas da integracao GLPI."""


class GlpiIntegrationError(Exception):
    """Erro seguro para persistencia e retorno interno."""


class GlpiConfigurationError(GlpiIntegrationError):
    pass


class GlpiApiError(GlpiIntegrationError):
    pass


class GlpiResponseError(GlpiIntegrationError):
    pass
