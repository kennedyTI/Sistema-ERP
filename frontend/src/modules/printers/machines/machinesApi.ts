import { getStoredToken } from "@/modules/auth/authStorage";
import { buildApiUrl } from "@/shared/lib/api-url";

export interface PrinterMachine {
  id: number;
  name: string;
  location: string | null;
}

interface ApiEnvelope<T> {
  success: boolean;
  data: T;
}

export async function fetchPrinterMachines(): Promise<PrinterMachine[]> {
  const token = getStoredToken();
  const response = await fetch(buildApiUrl("v2/printers/machines"), {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });

  if (!response.ok) throw new Error("Nao foi possivel consultar as maquinas.");

  const payload = (await response.json()) as ApiEnvelope<PrinterMachine[]>;
  return payload.data;
}
