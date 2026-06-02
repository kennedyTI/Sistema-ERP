"""
Arquivo: backend/app/core/timezone.py

Descricao:
- Centraliza timestamps operacionais do backend.

Objetivo:
- Garantir que datas criadas pelo Python usem America/Sao_Paulo.
- Evitar uso de datetime.utcnow() em models e services principais.

Regra:
- As tabelas atuais usam TIMESTAMP sem timezone.
- O sistema grava datetime sem tzinfo, ja convertido para horario local do Brasil.
"""

from datetime import datetime
from zoneinfo import ZoneInfo


SAO_PAULO_TIME_ZONE = "America/Sao_Paulo"
SAO_PAULO_ZONE = ZoneInfo(SAO_PAULO_TIME_ZONE)


# ---------------------------------------------------------------------
# TIMESTAMP OPERACIONAL LOCAL
# ---------------------------------------------------------------------
def now_sao_paulo() -> datetime:
    """
    Retorna o horario atual de Sao Paulo como datetime naive.
    """
    return datetime.now(SAO_PAULO_ZONE).replace(tzinfo=None)


# ---------------------------------------------------------------------
# TIMESTAMP COM TIMEZONE PARA LOGS/VALIDACOES
# ---------------------------------------------------------------------
def aware_now_sao_paulo() -> datetime:
    """
    Retorna o horario atual de Sao Paulo mantendo tzinfo.
    """
    return datetime.now(SAO_PAULO_ZONE)
