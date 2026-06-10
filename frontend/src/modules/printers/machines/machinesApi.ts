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
  image_url: string | null;
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

export interface PrinterMachineEditPayload {
  name: string;
  ip_address: string;
  model_id: number;
  sector: string | null;
  cost_center: string | null;
  notes: string | null;
  updated_at: string;
}

export interface PrinterMachineSummary {
  total_machines: number;
  active: number;
  inactive: number;
  manufacturers: number;
  registered_models: number;
}

export interface PrinterModelOption {
  id: number;
  manufacturer: string;
  model: string;
  type: string | null;
  color_mode: string | null;
  image_url: string | null;
}

export interface PrinterOperationalSummary {
  status: string;
  alert: string | null;
  message: string | null;
  last_checked_at: string | null;
}

export interface PrinterOperationalLog {
  id: number;
  event_type: string;
  previous_status: string | null;
  next_status: string | null;
  previous_alert: string | null;
  next_alert: string | null;
  message: string | null;
  checked_at: string;
  source: string;
}

export interface PrinterMachineDetails {
  machine: PrinterMachine;
  model: PrinterModelOption | null;
  operational_status: PrinterOperationalSummary | null;
  recent_logs: PrinterOperationalLog[];
  actions: {
    can_edit: boolean;
    can_toggle_status: boolean;
  };
}

export interface PrinterMachineToggleResult {
  machine: PrinterMachine;
  summary: PrinterMachineSummary;
  message: string;
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
  url_imagem: string | null;
  criado_em: string;
  atualizado_em: string;
}

interface ResumoMaquinasApi {
  total_maquinas: number;
  ativas: number;
  inativas: number;
  fabricantes: number;
  modelos_cadastrados: number;
}

interface ModeloImpressoraApi {
  id: number;
  fabricante: string;
  modelo: string;
  tipo: string | null;
  cor_modelo: string | null;
  url_imagem: string | null;
}

interface DetalhesMaquinaApi {
  maquina: MaquinaApi;
  modelo_dados: ModeloImpressoraApi | null;
  status_operacional: {
    status: string;
    alerta: string | null;
    mensagem: string | null;
    ultima_verificacao_em: string | null;
  } | null;
  logs_recentes: Array<{
    id: number;
    tipo_evento: string;
    status_anterior: string | null;
    status_novo: string | null;
    alerta_anterior: string | null;
    alerta_novo: string | null;
    mensagem: string | null;
    verificado_em: string;
    origem: string;
  }>;
  acoes: {
    pode_editar: boolean;
    pode_alternar_status: boolean;
  };
}

interface RespostaApi<T> {
  sucesso: boolean;
  dados: T | null;
  mensagem?: string | null;
  erros?: Record<string, string[]> | null;
}

interface MachinesResponse<T> {
  data: T;
  message: string | null;
}

export class MachinesApiError extends Error {
  readonly fieldErrors: Record<string, string[]>;
  readonly status: number;

  constructor(
    message: string,
    {
      fieldErrors = {},
      status = 0,
    }: {
      fieldErrors?: Record<string, string[]>;
      status?: number;
    } = {},
  ) {
    super(message);
    this.name = "MachinesApiError";
    this.fieldErrors = fieldErrors;
    this.status = status;
  }
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
    image_url: machine.url_imagem,
    created_at: machine.criado_em,
    updated_at: machine.atualizado_em,
  };
}

function mapSummary(summary: ResumoMaquinasApi): PrinterMachineSummary {
  return {
    total_machines: summary.total_maquinas,
    active: summary.ativas,
    inactive: summary.inativas,
    manufacturers: summary.fabricantes,
    registered_models: summary.modelos_cadastrados,
  };
}

function mapModel(model: ModeloImpressoraApi): PrinterModelOption {
  return {
    id: model.id,
    manufacturer: model.fabricante,
    model: model.modelo,
    type: model.tipo,
    color_mode: model.cor_modelo,
    image_url: model.url_imagem,
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

async function requestMachinesApi<T>(
  path: string,
  init: RequestInit = {},
): Promise<MachinesResponse<T>> {
  const token = getStoredToken();
  const response = await fetch(buildApiUrl(path), {
    ...init,
    headers: {
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(init.body ? { "Content-Type": "application/json" } : {}),
      ...init.headers,
    },
  });

  let payload: RespostaApi<T>;
  try {
    payload = (await response.json()) as RespostaApi<T>;
  } catch {
    throw new MachinesApiError("Não foi possível interpretar a resposta do servidor.", {
      status: response.status,
    });
  }

  if (!response.ok || !payload.sucesso || payload.dados === null) {
    throw new MachinesApiError(payload.mensagem ?? "Não foi possível concluir a operação.", {
      fieldErrors: payload.erros ?? {},
      status: response.status,
    });
  }

  return {
    data: payload.dados,
    message: payload.mensagem ?? null,
  };
}

export async function fetchPrinterMachines(): Promise<PrinterMachine[]> {
  const response = await requestMachinesApi<MaquinaApi[]>("v2/printers/machines");
  return response.data.map(mapMachine);
}

export async function fetchPrinterMachineSummary(): Promise<PrinterMachineSummary> {
  const response = await requestMachinesApi<ResumoMaquinasApi>("v2/printers/machines/summary");
  return mapSummary(response.data);
}

export async function fetchPrinterMachineDetails(
  machineId: number,
): Promise<PrinterMachineDetails> {
  const response = await requestMachinesApi<DetalhesMaquinaApi>(
    `v2/printers/machines/${machineId}/details`,
  );
  const details = response.data;

  return {
    machine: mapMachine(details.maquina),
    model: details.modelo_dados ? mapModel(details.modelo_dados) : null,
    operational_status: details.status_operacional
      ? {
          status: details.status_operacional.status,
          alert: details.status_operacional.alerta,
          message: details.status_operacional.mensagem,
          last_checked_at: details.status_operacional.ultima_verificacao_em,
        }
      : null,
    recent_logs: details.logs_recentes.map((log) => ({
      id: log.id,
      event_type: log.tipo_evento,
      previous_status: log.status_anterior,
      next_status: log.status_novo,
      previous_alert: log.alerta_anterior,
      next_alert: log.alerta_novo,
      message: log.mensagem,
      checked_at: log.verificado_em,
      source: log.origem,
    })),
    actions: {
      can_edit: details.acoes.pode_editar,
      can_toggle_status: details.acoes.pode_alternar_status,
    },
  };
}

export async function createPrinterMachine(
  payload: PrinterMachinePayload,
): Promise<PrinterMachine> {
  const response = await requestMachinesApi<{ maquina: MaquinaApi }>("v2/printers/machines", {
    method: "POST",
    body: JSON.stringify(requestPayload(payload)),
  });
  return mapMachine(response.data.maquina);
}

export async function updatePrinterMachine(
  machineId: number,
  payload: PrinterMachineEditPayload,
): Promise<{ machine: PrinterMachine; message: string }> {
  const response = await requestMachinesApi<{ maquina: MaquinaApi }>(
    `v2/printers/machines/${machineId}`,
    {
      method: "PATCH",
      body: JSON.stringify({
        nome: payload.name,
        endereco_ip: payload.ip_address,
        modelo_id: payload.model_id,
        setor: payload.sector,
        centro_custo: payload.cost_center,
        observacoes: payload.notes,
        atualizado_em: payload.updated_at,
      }),
    },
  );

  return {
    machine: mapMachine(response.data.maquina),
    message: response.message ?? "Máquina atualizada com sucesso.",
  };
}

export async function updatePrinterMachineStatus(
  machineId: number,
  isActive: boolean,
): Promise<PrinterMachineToggleResult> {
  const response = await requestMachinesApi<{
    maquina: MaquinaApi;
    resumo: ResumoMaquinasApi;
  }>(`v2/printers/machines/${machineId}/status`, {
    method: "PATCH",
    body: JSON.stringify({ ativo: isActive }),
  });

  return {
    machine: mapMachine(response.data.maquina),
    summary: mapSummary(response.data.resumo),
    message:
      response.message ??
      (isActive ? "Máquina ativada com sucesso." : "Máquina inativada com sucesso."),
  };
}
