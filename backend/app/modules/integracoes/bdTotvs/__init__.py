"""Integracao generica com banco TOTVS/Protheus em SQL Server."""

from backend.app.modules.integracoes.bdTotvs.config import (
    TotvsDbConfig,
    get_totvs_db_config,
)
from backend.app.modules.integracoes.bdTotvs.executor import (
    execute_query,
    execute_scalar,
)
from backend.app.modules.integracoes.bdTotvs.healthcheck import (
    TotvsHealthcheckResult,
    test_connection,
)

__all__ = [
    "TotvsDbConfig",
    "TotvsHealthcheckResult",
    "execute_query",
    "execute_scalar",
    "get_totvs_db_config",
    "test_connection",
]
