import { getStoredToken } from "@/modules/auth/authStorage";
import { buildApiUrl } from "@/shared/lib/api-url";

export interface DashboardStatus {
  module: "printers_dashboard";
  status: "development";
  message: string;
}

interface ApiEnvelope<T> {
  success: boolean;
  data: T;
}

export async function fetchPrinterDashboardStatus(): Promise<DashboardStatus> {
  const token = getStoredToken();
  const response = await fetch(buildApiUrl("v2/printers/dashboard"), {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });

  if (!response.ok) throw new Error("Nao foi possivel consultar o dashboard de impressoras.");

  const payload = (await response.json()) as ApiEnvelope<DashboardStatus>;
  return payload.data;
}
