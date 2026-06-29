import type {
  PrinterOperationalAlert,
  PrinterOperationalStatus,
  StatusSeverity,
} from "@/modules/printers/status/statusApi";

const severityWeight: Record<StatusSeverity, number> = {
  high: 50,
  medium: 40,
  low: 30,
  unknown: 20,
  green: 10,
};

function alertSeverityWeight(severity: StatusSeverity) {
  return severityWeight[severity] ?? severityWeight.unknown;
}

export function selectHighestSeverityAlerts(
  status: PrinterOperationalStatus,
): PrinterOperationalAlert[] {
  if (status.status_operacional !== "online") {
    return [
      {
        codigo: "sem_servico",
        mensagem: "Sem serviço",
        nivel_alerta: "vermelho",
        severidade: "high",
        prioridade: 6,
      },
    ];
  }

  const alerts = status.alertas?.length
    ? status.alertas
    : [
        {
          codigo: "status_atual",
          mensagem: status.alerta ?? status.mensagem_alerta ?? "Sem alerta informado",
          nivel_alerta: status.nivel_alerta,
          severidade: status.severidade,
          prioridade: Number.MAX_SAFE_INTEGER,
        },
      ];
  const highestWeight = Math.max(
    ...alerts.map((alert) => alertSeverityWeight(alert.severidade)),
  );

  return alerts.filter(
    (alert) => alertSeverityWeight(alert.severidade) === highestWeight,
  );
}
