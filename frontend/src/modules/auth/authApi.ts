import { clearStoredToken, getStoredToken } from "@/modules/auth/authStorage";
import { buildApiUrl } from "@/shared/lib/api-url";

const AUTH_BASE_PATH = "v2/auth";

interface ApiEnvelope<T> {
  success: boolean;
  data: T;
  message?: string | null;
  errors?: string[] | null;
}

export interface PortalPermissions {
  can_access_portal: boolean;
  can_access_admin: boolean;
  can_access_printers: boolean;
  can_access_printers_dashboard: boolean;
  can_access_printers_status: boolean;
  can_manage_printers_status: boolean;
  can_access_printers_machines: boolean;
  can_access_printers_paper: boolean;
}

export type PortalPermissionKey = keyof PortalPermissions;

export interface PrinterPermissions {
  ver_dashboard: boolean;
  ver_status: boolean;
  ver_maquinas: boolean;
  criar_maquinas: boolean;
  editar_maquinas: boolean;
  alternar_status_maquinas: boolean;
  ver_papel: boolean;
}

export interface PortalUser {
  id?: number | null;
  username: string;
  display_name: string;
  email: string | null;
  groups: string[];
  permissions: PortalPermissions;
  permissoes: {
    impressoras: PrinterPermissions;
  };
}

export interface LoginResponse {
  access_token: string;
  token_type: "bearer";
  user: PortalUser;
}

function authHeaders() {
  const token = getStoredToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function parseErrorMessage(response: Response, fallback: string) {
  try {
    const payload = (await response.json()) as Partial<ApiEnvelope<unknown>>;
    return payload.message ?? payload.errors?.[0] ?? fallback;
  } catch {
    return fallback;
  }
}

function handleUnauthorized() {
  clearStoredToken();
  if (typeof window !== "undefined" && window.location.pathname !== "/login") {
    window.location.assign("/login");
  }
}

async function authRequest<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(buildApiUrl(path), {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...authHeaders(),
      ...(init.headers ?? {}),
    },
  });

  if (!response.ok) {
    if (response.status === 401 && path !== `${AUTH_BASE_PATH}/login`) handleUnauthorized();
    throw new Error(await parseErrorMessage(response, "Usuario ou senha invalidos."));
  }

  return (await response.json()) as T;
}

export async function loginWithCredentials(username: string, password: string): Promise<LoginResponse> {
  return authRequest<LoginResponse>(`${AUTH_BASE_PATH}/login`, {
    method: "POST",
    body: JSON.stringify({ username, password }),
  });
}

export async function fetchCurrentUser(): Promise<PortalUser> {
  return authRequest<PortalUser>(`${AUTH_BASE_PATH}/me`, {
    method: "GET",
  });
}

export async function logoutSession(): Promise<void> {
  await authRequest(`${AUTH_BASE_PATH}/logout`, {
    method: "POST",
  });
}
