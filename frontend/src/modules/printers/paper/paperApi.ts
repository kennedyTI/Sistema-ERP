import { getStoredToken } from "@/modules/auth/authStorage";
import { buildApiUrl } from "@/shared/lib/api-url";

export interface PaperStatus {
  module: "printers_paper";
  status: "development";
  message: string;
}

interface ApiEnvelope<T> {
  success: boolean;
  data: T;
}

export async function fetchPrinterPaperStatus(): Promise<PaperStatus> {
  const token = getStoredToken();
  const response = await fetch(buildApiUrl("v2/printers/paper"), {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });

  if (!response.ok) throw new Error("Nao foi possivel consultar o submodulo Papel.");

  const payload = (await response.json()) as ApiEnvelope<PaperStatus>;
  return payload.data;
}
