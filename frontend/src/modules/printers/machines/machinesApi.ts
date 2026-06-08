import { getStoredToken } from "@/modules/auth/authStorage";
import { buildApiUrl } from "@/shared/lib/api-url";

export interface PrinterMachine {
  id: number;
  name: string;
  ip_address: string;
  model_id: number | null;
  manufacturer: string | null;
  model: string | null;
  type: string | null;
  color_mode: string | null;
  sector: string | null;
  cost_center: string | null;
  is_active: boolean;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface PrinterMachinePayload {
  name: string;
  ip_address: string;
  manufacturer?: string | null;
  model?: string | null;
  type?: string | null;
  color_mode?: string | null;
  sector?: string | null;
  cost_center?: string | null;
  is_active?: boolean;
  notes?: string | null;
}

interface ApiEnvelope<T> {
  success: boolean;
  data: T;
  message?: string | null;
  errors?: string[] | null;
}

async function requestMachinesApi<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = getStoredToken();
  const response = await fetch(buildApiUrl(path), {
    ...init,
    headers: {
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(init.body ? { "Content-Type": "application/json" } : {}),
      ...init.headers,
    },
  });

  const payload = (await response.json()) as ApiEnvelope<T>;

  if (!response.ok || !payload.success) {
    throw new Error(payload.errors?.[0] ?? payload.message ?? "Nao foi possivel concluir a operacao.");
  }

  return payload.data;
}

export async function fetchPrinterMachines(): Promise<PrinterMachine[]> {
  return requestMachinesApi<PrinterMachine[]>("v2/printers/machines");
}

export async function createPrinterMachine(payload: PrinterMachinePayload): Promise<PrinterMachine> {
  return requestMachinesApi<PrinterMachine>("v2/printers/machines", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function updatePrinterMachine(
  id: number,
  payload: PrinterMachinePayload,
): Promise<PrinterMachine> {
  return requestMachinesApi<PrinterMachine>(`v2/printers/machines/${id}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export async function updatePrinterMachineStatus(id: number, isActive: boolean): Promise<PrinterMachine> {
  return requestMachinesApi<PrinterMachine>(`v2/printers/machines/${id}/status`, {
    method: "PATCH",
    body: JSON.stringify({ is_active: isActive }),
  });
}
