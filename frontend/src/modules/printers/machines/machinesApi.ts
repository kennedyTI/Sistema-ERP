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

interface MaquinaApi {
  id: number;
  nome: string;
  endereco_ip: string;
  modelo_id: number | null;
  fabricante: string | null;
  modelo: string | null;
  tipo: string | null;
  cor_modelo: string | null;
  setor: string | null;
  centro_custo: string | null;
  ativo: boolean;
  observacoes: string | null;
  criado_em: string;
  atualizado_em: string;
}

interface RespostaApi<T> {
  sucesso: boolean;
  dados: T;
  mensagem?: string | null;
  erros?: Record<string, string[]> | null;
}

function mapMachine(machine: MaquinaApi): PrinterMachine {
  return {
    id: machine.id,
    name: machine.nome,
    ip_address: machine.endereco_ip,
    model_id: machine.modelo_id,
    manufacturer: machine.fabricante,
    model: machine.modelo,
    type: machine.tipo,
    color_mode: machine.cor_modelo,
    sector: machine.setor,
    cost_center: machine.centro_custo,
    is_active: machine.ativo,
    notes: machine.observacoes,
    created_at: machine.criado_em,
    updated_at: machine.atualizado_em,
  };
}

function requestPayload(payload: PrinterMachinePayload) {
  return {
    nome: payload.name,
    endereco_ip: payload.ip_address,
    fabricante: payload.manufacturer,
    modelo: payload.model,
    tipo: payload.type,
    cor_modelo: payload.color_mode,
    setor: payload.sector,
    centro_custo: payload.cost_center,
    ativo: payload.is_active,
    observacoes: payload.notes,
  };
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

  const payload = (await response.json()) as RespostaApi<T>;

  if (!response.ok || !payload.sucesso) {
    const fieldError = payload.erros ? Object.values(payload.erros).flat()[0] : null;
    throw new Error(fieldError ?? payload.mensagem ?? "Nao foi possivel concluir a operacao.");
  }

  return payload.dados;
}

export async function fetchPrinterMachines(): Promise<PrinterMachine[]> {
  const machines = await requestMachinesApi<MaquinaApi[]>("v2/printers/machines");
  return machines.map(mapMachine);
}

export async function createPrinterMachine(payload: PrinterMachinePayload): Promise<PrinterMachine> {
  const result = await requestMachinesApi<{ maquina: MaquinaApi }>("v2/printers/machines", {
    method: "POST",
    body: JSON.stringify(requestPayload(payload)),
  });
  return mapMachine(result.maquina);
}

export async function updatePrinterMachine(
  machine: PrinterMachine,
  payload: PrinterMachinePayload,
): Promise<PrinterMachine> {
  const result = await requestMachinesApi<{ maquina: MaquinaApi }>(
    `v2/printers/machines/${machine.id}`,
    {
      method: "PATCH",
      body: JSON.stringify({
        nome: payload.name,
        endereco_ip: payload.ip_address,
        modelo_id: machine.model_id,
        setor: payload.sector,
        centro_custo: payload.cost_center,
        observacoes: payload.notes,
        atualizado_em: machine.updated_at,
      }),
    },
  );
  return mapMachine(result.maquina);
}

export async function updatePrinterMachineStatus(id: number, isActive: boolean): Promise<PrinterMachine> {
  const result = await requestMachinesApi<{ maquina: MaquinaApi }>(
    `v2/printers/machines/${id}/status`,
    {
      method: "PATCH",
      body: JSON.stringify({ ativo: isActive }),
    },
  );
  return mapMachine(result.maquina);
}
