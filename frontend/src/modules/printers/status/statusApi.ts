import { getStoredToken } from "@/modules/auth/authStorage";
import { buildApiUrl } from "@/shared/lib/api-url";

export type OperationalStatus = "desconhecido" | "online" | "offline" | "erro";
export type AlertLevel = "cinza" | "verde" | "amarelo" | "vermelho";

export interface PrinterOperationalStatus {
  machine_id: number;
  machine_name: string;
  ip_address: string;
  manufacturer: string | null;
  model: string | null;
  sector: string | null;
  cost_center: string | null;
  status_operacional: OperationalStatus;
  nivel_alerta: AlertLevel;
  mensagem_alerta: string | null;
  ultima_verificacao_em: string | null;
  ultimo_sucesso_em: string | null;
  ultima_falha_em: string | null;
  tempo_resposta_ms: number | null;
  origem: "sistema" | "manual" | "seed" | "futuro_snmp";
}

interface ApiEnvelope<T> {
  success: boolean;
  data: T;
  message?: string | null;
  errors?: string[] | null;
}

export async function fetchPrinterStatuses(): Promise<PrinterOperationalStatus[]> {
  const token = getStoredToken();
  const response = await fetch(buildApiUrl("v2/printers/status"), {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  const payload = (await response.json()) as ApiEnvelope<PrinterOperationalStatus[]>;

  if (!response.ok || !payload.success) {
    throw new Error(payload.errors?.[0] ?? payload.message ?? "Nao foi possivel consultar os status.");
  }

  return payload.data;
}
