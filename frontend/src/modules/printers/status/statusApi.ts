import { getStoredToken } from "@/modules/auth/authStorage";
import { buildApiUrl } from "@/shared/lib/api-url";

export type OperationalStatus = "online" | "offline";
export type ConfirmationMethod = "icmp" | "tcp" | "snmp" | "html" | "fallback";
export type AlertLevel = "cinza" | "verde" | "amarelo" | "vermelho";

export interface PrinterOperationalStatus {
  machine_id: number;
  machine_name: string;
  ip_address: string;
  manufacturer: string | null;
  model: string | null;
  url_imagem: string | null;
  sector: string | null;
  cost_center: string | null;
  status_operacional: OperationalStatus;
  nivel_alerta: AlertLevel;
  mensagem_alerta: string | null;
  mensagem_operador: string;
  ultima_verificacao_em: string | null;
  ultimo_sucesso_em: string | null;
  ultima_falha_em: string | null;
  tempo_resposta_ms: number | null;
  metodo_confirmacao: ConfirmationMethod | null;
  origem: "sistema" | "manual" | "seed" | "futuro_snmp";
  resposta_bruta: string | null;
}

export interface PrinterStatusSummary {
  total_impressoras: number;
  online: number;
  offline: number;
  com_alerta: number;
  substituir_toner: number;
}

export interface PrinterOperationalLog {
  id: number;
  machine_id: number;
  tipo_evento: string;
  status_anterior: string | null;
  status_novo: string | null;
  alerta_anterior: string | null;
  alerta_novo: string | null;
  mensagem: string | null;
  verificado_em: string;
  tempo_resposta_ms: number | null;
  origem: string;
  resposta_bruta: string | null;
  criado_em: string;
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
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  const payload = (await response.json()) as ApiEnvelope<T>;

  if (!response.ok || !payload.success) {
    throw new Error(
      payload.errors?.[0] ?? payload.message ?? "Nao foi possivel consultar os status.",
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
