"""Probes leves usados na cascata de conectividade."""

from __future__ import annotations

import math
import platform
import socket
import subprocess
from time import perf_counter

import requests
from pysnmp.hlapi import (
    CommunityData,
    ContextData,
    ObjectIdentity,
    ObjectType,
    SnmpEngine,
    UdpTransportTarget,
    getCmd,
)

from backend.app.modules.printers.monitoring.config import MonitoringSettings
from backend.app.modules.printers.monitoring.schemas import ConnectivityDetection, ProbeResult


SYS_NAME_OID = "1.3.6.1.2.1.1.5.0"
HTTP_STATUS_PATH = "/home/status.html"


def _latency_ms(started_at: float) -> int:
    return max(0, round((perf_counter() - started_at) * 1000))


def probe_icmp(host: str, timeout_seconds: float) -> ProbeResult:
    started_at = perf_counter()
    if platform.system().lower() == "windows":
        command = ["ping", "-n", "1", "-w", str(round(timeout_seconds * 1000)), host]
    else:
        command = ["ping", "-c", "1", "-W", str(max(1, math.ceil(timeout_seconds))), host]

    try:
        completed = subprocess.run(
            command,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=timeout_seconds + 0.5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ProbeResult(method="icmp", success=False, error="timeout")

    if completed.returncode == 0:
        return ProbeResult(method="icmp", success=True, latency_ms=_latency_ms(started_at))
    return ProbeResult(method="icmp", success=False, error="sem_resposta")


def probe_tcp(
    host: str,
    timeout_seconds: float,
    ports: tuple[int, ...] = (443, 80),
) -> ProbeResult:
    attempts: list[dict[str, int | bool | str]] = []
    for port in ports:
        started_at = perf_counter()
        try:
            with socket.create_connection((host, port), timeout=timeout_seconds):
                latency_ms = _latency_ms(started_at)
                attempts.append({"porta": port, "sucesso": True, "latencia_ms": latency_ms})
                return ProbeResult(
                    method="tcp",
                    success=True,
                    latency_ms=latency_ms,
                    details={"porta": port, "portas": attempts},
                )
        except (TimeoutError, OSError):
            attempts.append({"porta": port, "sucesso": False, "erro": "sem_resposta"})

    return ProbeResult(
        method="tcp",
        success=False,
        error="sem_resposta",
        details={"portas": attempts},
    )


def probe_snmp(host: str, settings: MonitoringSettings) -> ProbeResult:
    if not settings.snmp_community:
        return ProbeResult(method="snmp", success=False, error="nao_configurado")

    started_at = perf_counter()
    try:
        response = next(
            getCmd(
                SnmpEngine(),
                CommunityData(settings.snmp_community, mpModel=1),
                UdpTransportTarget(
                    (host, 161),
                    timeout=settings.snmp_timeout_seconds,
                    retries=0,
                ),
                ContextData(),
                ObjectType(ObjectIdentity(SYS_NAME_OID)),
            )
        )
        error_indication, error_status, _, var_binds = response
    except Exception:
        return ProbeResult(method="snmp", success=False, error="sem_resposta")

    if error_indication or error_status or not var_binds:
        return ProbeResult(method="snmp", success=False, error="sem_resposta")
    value = str(var_binds[0][1]).strip()
    if not value:
        return ProbeResult(method="snmp", success=False, error="resposta_vazia")
    return ProbeResult(
        method="snmp",
        success=True,
        latency_ms=_latency_ms(started_at),
        details={"oid": SYS_NAME_OID, "valor_recebido": True},
    )


def probe_html(host: str, timeout_seconds: float) -> ProbeResult:
    started_at = perf_counter()
    try:
        response = requests.get(
            f"http://{host}{HTTP_STATUS_PATH}",
            timeout=timeout_seconds,
            allow_redirects=False,
        )
    except requests.RequestException:
        return ProbeResult(method="html", success=False, error="sem_resposta")

    return ProbeResult(
        method="html",
        success=True,
        latency_ms=_latency_ms(started_at),
        details={"caminho": HTTP_STATUS_PATH, "status_http": response.status_code},
    )


def detect_connectivity(
    host: str,
    settings: MonitoringSettings | None = None,
) -> ConnectivityDetection:
    config = settings or MonitoringSettings()
    attempts: dict[str, dict] = {
        "icmp": {"executado": False},
        "tcp": {"executado": False},
        "snmp": {"executado": False},
        "html": {"executado": False},
    }
    probes = (
        lambda: probe_icmp(host, config.icmp_timeout_seconds),
        lambda: probe_tcp(host, config.tcp_timeout_seconds),
        lambda: probe_snmp(host, config),
        lambda: probe_html(host, config.http_timeout_seconds),
    )

    for run_probe in probes:
        result = run_probe()
        attempts[result.method] = result.as_attempt()
        if result.success:
            return ConnectivityDetection(
                online=True,
                method=result.method,
                latency_ms=result.latency_ms,
                attempts=attempts,
            )

    return ConnectivityDetection(
        online=False,
        method="fallback",
        latency_ms=None,
        attempts=attempts,
    )
