import { useEffect, useMemo, useState } from "react";
import {
  Activity,
  Check,
  CircleAlert,
  Edit3,
  Loader2,
  Power,
  PowerOff,
  Printer,
  RefreshCw,
  Save,
  X,
} from "lucide-react";
import { toast } from "sonner";

import {
  fetchPrinterMachineDetails,
  MachinesApiError,
  type PrinterMachine,
  type PrinterMachineDetails,
  type PrinterMachineEditPayload,
  type PrinterMachineToggleResult,
  type PrinterModelOption,
  updatePrinterMachine,
  updatePrinterMachineStatus,
} from "@/modules/printers/machines/machinesApi";
import { PrinterModelImage } from "@/modules/printers/shared/PrinterModelImage";
import { Alert, AlertDescription, AlertTitle } from "@/shared/ui/alert";
import { Badge } from "@/shared/ui/badge";
import { Button } from "@/shared/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/shared/ui/dialog";
import { Input } from "@/shared/ui/input";
import { Label } from "@/shared/ui/label";
import { ScrollArea } from "@/shared/ui/scroll-area";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/shared/ui/select";
import { Separator } from "@/shared/ui/separator";
import { cn } from "@/shared/lib/utils";

type EditableField =
  | "nome"
  | "endereco_ip"
  | "modelo_id"
  | "setor"
  | "centro_custo"
  | "observacoes";

interface MachineEditForm {
  name: string;
  ip_address: string;
  model_id: string;
  sector: string;
  cost_center: string;
  notes: string;
}

const operationalStatusLabels: Record<string, string> = {
  desconhecido: "Desconhecido",
  online: "Online",
  offline: "Offline",
  erro: "Erro",
};

const operationalStatusStyles: Record<string, string> = {
  desconhecido: "border-muted-foreground/30 bg-muted text-muted-foreground",
  online: "border-emerald-500/30 bg-emerald-500/12 text-emerald-700 dark:text-emerald-300",
  offline: "border-red-500/30 bg-red-500/12 text-red-700 dark:text-red-300",
  erro: "border-orange-500/30 bg-orange-500/12 text-orange-700 dark:text-orange-300",
};

const operationalAlertStyles = {
  neutral: "border-muted-foreground/30 bg-muted/70 text-muted-foreground",
  warning: "border-amber-400/40 bg-amber-500/12 text-amber-700 dark:text-amber-300",
  critical: "border-red-500/30 bg-red-500/12 text-red-700 dark:text-red-300",
  normal: "border-emerald-500/30 bg-emerald-500/12 text-emerald-700 dark:text-emerald-300",
} as const;

export function MachineDetailsDialog({
  machine,
  open,
  modelOptions,
  canEdit,
  canToggle,
  onOpenChange,
  onMachineUpdated,
  onMachineToggled,
}: {
  machine: PrinterMachine | null;
  open: boolean;
  modelOptions: PrinterModelOption[];
  canEdit: boolean;
  canToggle: boolean;
  onOpenChange: (open: boolean) => void;
  onMachineUpdated: (machine: PrinterMachine) => void;
  onMachineToggled: (result: PrinterMachineToggleResult) => void;
}) {
  const [details, setDetails] = useState<PrinterMachineDetails | null>(null);
  const [loading, setLoading] = useState(false);
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [toggling, setToggling] = useState(false);
  const [generalError, setGeneralError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string[]>>({});
  const [savedFields, setSavedFields] = useState<Set<EditableField>>(new Set());
  const [form, setForm] = useState<MachineEditForm>(() => emptyEditForm());

  const machineId = machine?.id;
  const currentMachine = details?.machine ?? machine;
  const currentModelOptions = useMemo(() => {
    if (!currentMachine?.model_id) return modelOptions;
    if (modelOptions.some((option) => option.id === currentMachine.model_id)) return modelOptions;
    if (!currentMachine.manufacturer || !currentMachine.model) return modelOptions;

    return [
      ...modelOptions,
      {
        id: currentMachine.model_id,
        manufacturer: currentMachine.manufacturer,
        model: currentMachine.model,
        type: currentMachine.type,
        color_mode: currentMachine.color_mode,
        image_url: currentMachine.image_url,
      },
    ];
  }, [currentMachine, modelOptions]);

  useEffect(() => {
    if (!open || !machineId) return;
    setDetails(null);
    setEditing(false);
    setGeneralError(null);
    setFieldErrors({});
    setSavedFields(new Set());
    void loadDetails(machineId, false);
  }, [machineId, open]);

  useEffect(() => {
    if (savedFields.size === 0) return;
    const timeout = window.setTimeout(() => setSavedFields(new Set()), 3500);
    return () => window.clearTimeout(timeout);
  }, [savedFields]);

  async function loadDetails(machineId: number, keepEditing: boolean) {
    setLoading(true);
    setGeneralError(null);
    try {
      const nextDetails = await fetchPrinterMachineDetails(machineId);
      setDetails(nextDetails);
      if (keepEditing) {
        setForm(toEditForm(nextDetails.machine));
        setFieldErrors({});
      }
    } catch (error) {
      const message =
        error instanceof Error
          ? error.message
          : "Não foi possível carregar os detalhes da máquina.";
      setGeneralError(message);
      toast.error(message);
    } finally {
      setLoading(false);
    }
  }

  function handleOpenChange(nextOpen: boolean) {
    if (!nextOpen) resetDialogState();
    onOpenChange(nextOpen);
  }

  function resetDialogState() {
    setDetails(null);
    setEditing(false);
    setSaving(false);
    setToggling(false);
    setGeneralError(null);
    setFieldErrors({});
    setSavedFields(new Set());
  }

  function beginEditing() {
    if (!currentMachine) return;
    setForm(toEditForm(currentMachine));
    setFieldErrors({});
    setGeneralError(null);
    setSavedFields(new Set());
    setEditing(true);
  }

  function cancelEditing() {
    if (currentMachine) setForm(toEditForm(currentMachine));
    setEditing(false);
    setFieldErrors({});
    setGeneralError(null);
    setSavedFields(new Set());
  }

  async function saveChanges() {
    if (!currentMachine) return;

    const modelId = Number(form.model_id);
    if (!Number.isInteger(modelId) || modelId <= 0) {
      setFieldErrors({ modelo_id: ["Selecione um modelo de impressora."] });
      setGeneralError("Não foi possível validar os dados da máquina.");
      return;
    }

    const changedFields = findChangedFields(currentMachine, form);
    const payload: PrinterMachineEditPayload = {
      name: form.name.trim(),
      ip_address: form.ip_address.trim(),
      model_id: modelId,
      sector: cleanOptional(form.sector),
      cost_center: cleanOptional(form.cost_center),
      notes: cleanOptional(form.notes),
      // O backend compara esta versão com a linha bloqueada e retorna 409
      // quando outra edição foi salva depois da abertura do modal.
      updated_at: currentMachine.updated_at,
    };

    setSaving(true);
    setGeneralError(null);
    setFieldErrors({});
    try {
      const result = await updatePrinterMachine(currentMachine.id, payload);
      const selectedModel =
        currentModelOptions.find((option) => option.id === result.machine.model_id) ?? null;
      setDetails((current) =>
        current
          ? {
              ...current,
              machine: result.machine,
              model: selectedModel,
            }
          : current,
      );
      setSavedFields(changedFields);
      setEditing(false);
      onMachineUpdated(result.machine);
      toast.success(result.message);
    } catch (error) {
      const apiError =
        error instanceof MachinesApiError
          ? error
          : new MachinesApiError(
              error instanceof Error ? error.message : "Não foi possível atualizar a máquina.",
            );
      setGeneralError(apiError.message);
      setFieldErrors(apiError.fieldErrors);
      toast.error(apiError.message);
    } finally {
      setSaving(false);
    }
  }

  async function toggleMachineStatus() {
    if (!currentMachine) return;

    setToggling(true);
    setGeneralError(null);
    try {
      const result = await updatePrinterMachineStatus(currentMachine.id, !currentMachine.is_active);
      setDetails((current) =>
        current
          ? {
              ...current,
              machine: result.machine,
            }
          : current,
      );
      onMachineToggled(result);
      toast.success(result.message);
    } catch (error) {
      const message =
        error instanceof Error ? error.message : "Não foi possível alterar o status da máquina.";
      setGeneralError(message);
      toast.error(message);
    } finally {
      setToggling(false);
    }
  }

  // A interface exige concordância entre a sessão e as ações devolvidas para
  // o registro; esconder botões não substitui a autorização feita pela API.
  const detailsCanEdit = Boolean(canEdit && details?.actions.can_edit);
  const detailsCanToggle = Boolean(canToggle && details?.actions.can_toggle_status);

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="h-[min(92dvh,780px)] max-w-[1180px] grid-rows-[auto_minmax(0,1fr)_auto] gap-0 overflow-hidden p-0">
        <div className="border-b border-border px-4 py-3.5 pr-14 sm:px-5 sm:py-4">
          <DialogHeader>
            <div className="flex flex-wrap items-center gap-3">
              <DialogTitle>{editing ? "Editar máquina" : "Detalhes da máquina"}</DialogTitle>
              {currentMachine && <RegistrationStatusBadge active={currentMachine.is_active} />}
            </div>
            <DialogDescription>
              {editing
                ? "Atualize os dados cadastrais sem alterar o status operacional."
                : "Consulta cadastral, estado operacional e eventos recentes."}
            </DialogDescription>
          </DialogHeader>
        </div>

        {!currentMachine ? (
          <div className="flex min-h-80 items-center justify-center text-sm text-muted-foreground">
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            Carregando máquina...
          </div>
        ) : (
          <ScrollArea className="min-h-0">
            <div className="space-y-4 px-4 py-3.5 sm:px-5 sm:py-4">
              {loading && (
                <div className="flex items-center gap-2 text-sm text-muted-foreground">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Atualizando detalhes...
                </div>
              )}

              {generalError && (
                <Alert variant="destructive">
                  <CircleAlert className="h-4 w-4" />
                  <AlertTitle>Não foi possível concluir a operação</AlertTitle>
                  <AlertDescription className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                    <span>
                      {fieldErrors.atualizado_em
                        ? "Esta máquina foi alterada por outro usuário. Atualize os dados antes de salvar."
                        : generalError}
                    </span>
                    {fieldErrors.atualizado_em && (
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        onClick={() => void loadDetails(currentMachine.id, true)}
                        disabled={loading}
                      >
                        <RefreshCw className="h-4 w-4" />
                        Recarregar detalhes
                      </Button>
                    )}
                  </AlertDescription>
                </Alert>
              )}

              <div className="grid gap-4 lg:grid-cols-[280px_minmax(0,1fr)]">
                <PrinterModelImage
                  imageUrl={currentMachine.image_url}
                  model={currentMachine.model}
                  equipmentName={currentMachine.name}
                />

                {editing ? (
                  <EditForm
                    form={form}
                    fieldErrors={fieldErrors}
                    modelOptions={currentModelOptions}
                    onChange={setForm}
                  />
                ) : (
                  <MachineData machine={currentMachine} savedFields={savedFields} />
                )}
              </div>

              <Separator />

              <OperationalData details={details} />

              <Separator />

              <RecentLogs logs={details?.recent_logs ?? []} />
            </div>
          </ScrollArea>
        )}

        <DialogFooter className="shrink-0 border-t border-border bg-card/95 px-4 py-3 sm:px-5 sm:py-3.5">
          {editing ? (
            <>
              <Button type="button" variant="outline" onClick={cancelEditing} disabled={saving}>
                Cancelar
              </Button>
              <Button type="button" onClick={() => void saveChanges()} disabled={saving || loading}>
                {saving ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Save className="h-4 w-4" />
                )}
                Salvar
              </Button>
            </>
          ) : (
            <>
              {detailsCanEdit && (
                <Button type="button" variant="outline" onClick={beginEditing} disabled={loading}>
                  <Edit3 className="h-4 w-4" />
                  Editar
                </Button>
              )}
              {detailsCanToggle && (
                <Button
                  type="button"
                  variant={currentMachine?.is_active ? "destructive" : "default"}
                  onClick={() => void toggleMachineStatus()}
                  disabled={toggling || loading}
                >
                  {toggling ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : currentMachine?.is_active ? (
                    <PowerOff className="h-4 w-4" />
                  ) : (
                    <Power className="h-4 w-4" />
                  )}
                  {currentMachine?.is_active ? "Inativar" : "Ativar"}
                </Button>
              )}
            </>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function MachineData({
  machine,
  savedFields,
}: {
  machine: PrinterMachine;
  savedFields: Set<EditableField>;
}) {
  return (
    <section>
      <div className="flex items-start gap-3">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-md bg-primary/10 text-primary">
          <Printer className="h-5 w-5" />
        </div>
        <div>
          <h3 className="text-xl font-semibold">{machine.name}</h3>
          <p className="mt-1 text-sm text-muted-foreground">{machine.ip_address}</p>
        </div>
      </div>

      <div className="mt-5 grid gap-x-6 gap-y-4 sm:grid-cols-2 xl:grid-cols-3">
        <Detail label="Nome da máquina" value={machine.name} success={savedFields.has("nome")} />
        <Detail label="IP" value={machine.ip_address} success={savedFields.has("endereco_ip")} />
        <Detail label="Fabricante" value={machine.manufacturer} />
        <Detail label="Modelo" value={machine.model} success={savedFields.has("modelo_id")} />
        <Detail label="Setor" value={machine.sector} success={savedFields.has("setor")} />
        <Detail
          label="Centro de custo"
          value={machine.cost_center}
          success={savedFields.has("centro_custo")}
        />
        <Detail label="Status cadastral" value={machine.is_active ? "Ativa" : "Inativa"} />
        <Detail label="Criado em" value={formatDateTime(machine.created_at)} />
        <Detail label="Atualizado em" value={formatDateTime(machine.updated_at)} />
      </div>

      <div className="mt-5">
        <Detail
          label="Observações"
          value={machine.notes}
          success={savedFields.has("observacoes")}
        />
      </div>
    </section>
  );
}

function EditForm({
  form,
  fieldErrors,
  modelOptions,
  onChange,
}: {
  form: MachineEditForm;
  fieldErrors: Record<string, string[]>;
  modelOptions: PrinterModelOption[];
  onChange: (form: MachineEditForm) => void;
}) {
  return (
    <div className="grid gap-4 sm:grid-cols-2">
      <EditField label="Nome da máquina" error={fieldErrors.nome?.[0]}>
        <Input
          value={form.name}
          onChange={(event) => onChange({ ...form, name: event.target.value })}
          maxLength={160}
          required
        />
      </EditField>

      <EditField label="IP" error={fieldErrors.endereco_ip?.[0]}>
        <Input
          value={form.ip_address}
          onChange={(event) => onChange({ ...form, ip_address: event.target.value })}
          maxLength={45}
          required
        />
      </EditField>

      <EditField label="Modelo" error={fieldErrors.modelo_id?.[0]}>
        <Select
          value={form.model_id}
          onValueChange={(value) => onChange({ ...form, model_id: value })}
        >
          <SelectTrigger>
            <SelectValue placeholder="Selecione um modelo" />
          </SelectTrigger>
          <SelectContent>
            {modelOptions.map((option) => (
              <SelectItem key={option.id} value={String(option.id)}>
                {option.manufacturer} - {option.model}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </EditField>

      <EditField label="Setor" error={fieldErrors.setor?.[0]}>
        <Input
          value={form.sector}
          onChange={(event) => onChange({ ...form, sector: event.target.value })}
          maxLength={120}
        />
      </EditField>

      <EditField label="Centro de custo" error={fieldErrors.centro_custo?.[0]}>
        <Input
          value={form.cost_center}
          onChange={(event) => onChange({ ...form, cost_center: event.target.value })}
          maxLength={80}
        />
      </EditField>

      <EditField label="Observações" error={fieldErrors.observacoes?.[0]} className="sm:col-span-2">
        <textarea
          value={form.notes}
          onChange={(event) => onChange({ ...form, notes: event.target.value })}
          className="min-h-28 w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
        />
      </EditField>
    </div>
  );
}

function EditField({
  label,
  error,
  className,
  children,
}: {
  label: string;
  error?: string;
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <div className={cn("space-y-1.5", className)}>
      <div className="flex min-h-5 items-center justify-between gap-2">
        <Label>{label}</Label>
        {error && (
          <span className="inline-flex items-center gap-1 text-xs font-medium text-destructive">
            <X className="h-3.5 w-3.5" aria-hidden="true" />
            Erro
          </span>
        )}
      </div>
      {error && <p className="text-xs font-medium text-destructive">{error}</p>}
      {children}
    </div>
  );
}

function OperationalData({ details }: { details: PrinterMachineDetails | null }) {
  const operational = details?.operational_status;
  const statusKey = operational?.status ?? "desconhecido";

  return (
    <section>
      <div className="flex items-center gap-2">
        <Activity className="h-4 w-4 text-primary" />
        <h3 className="text-sm font-semibold">Estado operacional</h3>
      </div>
      <div className="mt-4 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <div>
          <p className="text-xs font-medium uppercase text-muted-foreground">Status operacional</p>
          <Badge
            variant="outline"
            className={cn(
              "mt-2",
              operationalStatusStyles[statusKey] ?? operationalStatusStyles.desconhecido,
            )}
          >
            {operationalStatusLabels[statusKey] ?? statusKey}
          </Badge>
        </div>
        <div>
          <p className="text-xs font-medium uppercase text-muted-foreground">Alerta</p>
          <Badge
            variant="outline"
            className={cn("mt-2 max-w-full", getOperationalAlertStyle(operational))}
          >
            <span className="truncate">{operational?.alert || "-"}</span>
          </Badge>
        </div>
        <Detail label="Mensagem operacional" value={operational?.message} />
        <Detail
          label="Última atualização operacional"
          value={formatDateTime(operational?.last_checked_at)}
        />
      </div>
    </section>
  );
}

function getOperationalAlertStyle(operational: PrinterMachineDetails["operational_status"]) {
  if (!operational?.alert) return operationalAlertStyles.neutral;
  if (operational.status === "offline") return operationalAlertStyles.critical;

  const alertText = operational.alert
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase();

  if (
    alertText.includes("sem servico") ||
    alertText.includes("falha") ||
    alertText.includes("critico")
  ) {
    return operationalAlertStyles.critical;
  }

  if (
    alertText.includes("toner") ||
    alertText.includes("cilindro") ||
    alertText.includes("tambor") ||
    alertText.includes("substituir")
  ) {
    return operationalAlertStyles.warning;
  }

  if (operational.status === "online") return operationalAlertStyles.normal;
  return operationalAlertStyles.neutral;
}

function RecentLogs({ logs }: { logs: PrinterMachineDetails["recent_logs"] }) {
  return (
    <section>
      <div className="flex items-center gap-2">
        <Activity className="h-4 w-4 text-primary" />
        <h3 className="text-sm font-semibold">Logs recentes</h3>
      </div>
      {logs.length === 0 ? (
        <p className="mt-3 text-sm text-muted-foreground">Nenhum evento operacional registrado.</p>
      ) : (
        <div className="mt-3 divide-y divide-border rounded-lg border border-border">
          {logs.map((log) => (
            <div
              key={log.id}
              className="grid gap-2 px-4 py-3 sm:grid-cols-[180px_minmax(0,1fr)_auto] sm:items-center"
            >
              <div>
                <p className="text-sm font-medium">{formatEventType(log.event_type)}</p>
                <p className="text-xs text-muted-foreground">{log.source}</p>
              </div>
              <div>
                <p className="text-sm">{log.message ?? "Evento sem mensagem."}</p>
                <p className="mt-1 text-xs text-muted-foreground">
                  {formatTransition(log.previous_status, log.next_status)}
                </p>
              </div>
              <time className="text-xs text-muted-foreground">
                {formatDateTime(log.checked_at)}
              </time>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

function Detail({
  label,
  value,
  success = false,
}: {
  label: string;
  value: string | null | undefined;
  success?: boolean;
}) {
  return (
    <div>
      <p className="flex items-center gap-1.5 text-xs font-medium uppercase text-muted-foreground">
        {label}
        {success && (
          <span className="inline-flex items-center gap-1 text-emerald-600 dark:text-emerald-400">
            <Check className="h-3.5 w-3.5" aria-hidden="true" />
            <span className="sr-only">Campo atualizado com sucesso</span>
          </span>
        )}
      </p>
      <p className="mt-1 text-sm">{value || "-"}</p>
    </div>
  );
}

function RegistrationStatusBadge({ active }: { active: boolean }) {
  return (
    <Badge
      variant="outline"
      className={
        active
          ? "border-emerald-500/35 bg-emerald-500/12 text-emerald-700 dark:text-emerald-300"
          : "border-red-500/35 bg-red-500/12 text-red-700 dark:text-red-300"
      }
    >
      Status cadastral: {active ? "Ativa" : "Inativa"}
    </Badge>
  );
}

function emptyEditForm(): MachineEditForm {
  return {
    name: "",
    ip_address: "",
    model_id: "",
    sector: "",
    cost_center: "",
    notes: "",
  };
}

function toEditForm(machine: PrinterMachine): MachineEditForm {
  return {
    name: machine.name,
    ip_address: machine.ip_address,
    model_id: machine.model_id ? String(machine.model_id) : "",
    sector: machine.sector ?? "",
    cost_center: machine.cost_center ?? "",
    notes: machine.notes ?? "",
  };
}

function findChangedFields(machine: PrinterMachine, form: MachineEditForm) {
  const changed = new Set<EditableField>();
  if (machine.name !== form.name.trim()) changed.add("nome");
  if (machine.ip_address !== form.ip_address.trim()) changed.add("endereco_ip");
  if (machine.model_id !== Number(form.model_id)) changed.add("modelo_id");
  if ((machine.sector ?? "") !== form.sector.trim()) changed.add("setor");
  if ((machine.cost_center ?? "") !== form.cost_center.trim()) changed.add("centro_custo");
  if ((machine.notes ?? "") !== form.notes.trim()) changed.add("observacoes");
  return changed;
}

function cleanOptional(value: string) {
  const normalized = value.trim();
  return normalized || null;
}

function formatDateTime(value: string | null | undefined) {
  if (!value) return "Sem registro";
  return new Intl.DateTimeFormat("pt-BR", {
    dateStyle: "short",
    timeStyle: "medium",
  }).format(new Date(value));
}

function formatEventType(value: string) {
  return value.replaceAll("_", " ").replace(/^\w/, (letter) => letter.toUpperCase());
}

function formatTransition(previous: string | null, next: string | null) {
  if (!previous && !next) return "Sem alteração de estado.";
  return `${previous ?? "-"} → ${next ?? "-"}`;
}
