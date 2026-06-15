"""Configuracao ambiental do monitoramento de conectividade."""

from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass(frozen=True)
class MonitoringSettings:
    cache_ttl_seconds: int = 90
    failure_threshold: int = 2
    global_lock_ttl_seconds: int = 300
    machine_lock_ttl_seconds: int = 30
    icmp_timeout_seconds: float = 1.0
    tcp_timeout_seconds: float = 1.0
    snmp_timeout_seconds: float = 1.0
    http_timeout_seconds: float = 2.0
    snmp_community: str = field(default="", repr=False)


def get_monitoring_settings() -> MonitoringSettings:
    return MonitoringSettings(
        cache_ttl_seconds=int(
            os.getenv("PRINTER_CONNECTIVITY_CACHE_TTL_SECONDS", "90")
        ),
        failure_threshold=int(
            os.getenv("PRINTER_CONNECTIVITY_FAILURE_THRESHOLD", "2")
        ),
        global_lock_ttl_seconds=int(
            os.getenv("PRINTER_CONNECTIVITY_GLOBAL_LOCK_TTL_SECONDS", "300")
        ),
        machine_lock_ttl_seconds=int(
            os.getenv("PRINTER_CONNECTIVITY_MACHINE_LOCK_TTL_SECONDS", "30")
        ),
        icmp_timeout_seconds=float(
            os.getenv("PRINTER_ICMP_TIMEOUT_SECONDS", "1")
        ),
        tcp_timeout_seconds=float(
            os.getenv("PRINTER_TCP_TIMEOUT_SECONDS", "1")
        ),
        snmp_timeout_seconds=float(
            os.getenv("PRINTER_SNMP_TIMEOUT_SECONDS", "1")
        ),
        http_timeout_seconds=float(
            os.getenv("PRINTER_HTTP_TIMEOUT_SECONDS", "2")
        ),
        snmp_community=os.getenv("PRINTER_SNMP_COMMUNITY", ""),
    )
