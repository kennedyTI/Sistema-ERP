import { getStoredToken } from "@/modules/auth/authStorage";
import { buildApiUrl } from "@/shared/lib/api-url";

export type OperationalStatus = "online" | "offline";
export type ConfirmationMethod = "icmp" | "tcp" | "snmp" | "html" | "fallback";
export type AlertLevel = "cinza" | "verde" | "amarelo" | "vermelho";
export type StatusSeverity = "unknown" | "green" | "low" | "medium" | "high";

export interface PrinterOperationalAlert {
  codigo: string;
  mensagem: string;
  nivel_alerta: AlertLevel;
  severidade: StatusSeverity;
  prioridade: number;
}

export interface PrinterOperationalToner {
  cor: "black" | "cyan" | "magenta" | "yellow" | "unknown";
  nome: string;
  percentual: number | null;
  descricao: string | null;
  origem_coleta: "snmp" | "html";
  metodo_coleta:
    | "printer_mib_walk"
    | "snmp_oid_fallback"
    | "web_status"
    | "brother_item_authenticated";
  coletado_em: string | null;
}

export interface PrinterOperationalStatus {
  machine_id: number;
  id: number;
  machine_name: string;
  maquina: string;
  ip_address: string;
  ip: string;
  manufacturer: string | null;
  fabricante: string | null;
  model: string | null;
  modelo: string | null;
  modelo_exibicao: string | null;
  url_imagem: string | null;
  sector: string | null;
  local: string | null;
  cost_center: string | null;
  status_operacional: OperationalStatus;
  status: OperationalStatus;
  nivel_alerta: AlertLevel;
  severidade: StatusSeverity;
  alerta: string | null;
  alertas: PrinterOperationalAlert[];
  toners: PrinterOperationalToner[];
  mensagem: string | null;
  mensagem_alerta: string | null;
  mensagem_operador: string;
  ultima_verificacao_em: string | null;
  verificado_em: string | null;
  ultimo_sucesso_em: string | null;
  ultima_falha_em: string | null;
  tempo_resposta_ms: number | null;
  metodo_confirmacao: ConfirmationMethod | null;
  origem: "sistema" | "manual" | "seed" | "futuro_snmp";
}

export interface PrinterStatusSummary {
  total_impressoras: number;
  online: number;
  offline: number;
  com_alerta: number;
  substituir_toner: number;
}

export interface PrinterOperationalLog {
  id: string;
  data_hora: string;
  tipo: string;
  mensagem: string;
  origem: "status" | "alerta";
}

interface ApiEnvelope<T> {
  success: boolean;
  data: T;
  message?: string | null;
  errors?: string[] | null;
}

async function requestStatusApi<T>(path: string): Promise<T> {
  const token = getStoredToken();
  const response = await fetch(buildApiUrl(path), {
    cache: "no-store",
    headers: {
      "Cache-Control": "no-cache",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
  });
  const contentType = response.headers.get("content-type") ?? "";
  const payload = contentType.includes("application/json")
    ? ((await response.json()) as ApiEnvelope<T>)
    : null;

  if (!response.ok || !payload?.success) {
    throw new Error(
      payload?.errors?.[0] ??
        payload?.message ??
        `Nao foi possivel consultar os status (HTTP ${response.status}).`,
    );
  }

  return payload.data;
}

export function fetchPrinterStatuses(): Promise<PrinterOperationalStatus[]> {
  return requestStatusApi<PrinterOperationalStatus[]>("v2/printers/status");
}

export function fetchPrinterStatusSummary(): Promise<PrinterStatusSummary> {
  return requestStatusApi<PrinterStatusSummary>("v2/printers/status/summary");
}

export function fetchPrinterStatusDetail(machineId: number): Promise<PrinterOperationalStatus> {
  return requestStatusApi<PrinterOperationalStatus>(`v2/printers/status/${machineId}`);
}

export function fetchPrinterStatusLogs(machineId: number): Promise<PrinterOperationalLog[]> {
  return requestStatusApi<PrinterOperationalLog[]>(`v2/printers/status/${machineId}/logs`);
}
