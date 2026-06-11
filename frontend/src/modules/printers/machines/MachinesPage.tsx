import { useEffect, useMemo, useRef, useState, type PointerEvent } from "react";
import {
  ArrowDownAZ,
  ArrowUpAZ,
  ChevronsUpDown,
  Columns3,
  GripVertical,
  Loader2,
  Plus,
  Power,
  PowerOff,
  Printer,
  RotateCcw,
} from "lucide-react";
import { toast } from "sonner";

import { RequireAuth } from "@/modules/auth/RequireAuth";
import { useAuth } from "@/modules/auth/authStore";
import { MachineDetailsDialog } from "@/modules/printers/machines/components/MachineDetailsDialog";
import { MachineFormDialog } from "@/modules/printers/machines/components/MachineFormDialog";
import { MachinesSummaryCards } from "@/modules/printers/machines/components/MachinesSummaryCards";
import { ColumnDragPreview } from "@/modules/printers/shared/ColumnDragPreview";
import {
  createPrinterMachine,
  fetchPrinterMachines,
  fetchPrinterMachineSummary,
  MachinesApiError,
  type PrinterMachine,
  type PrinterMachinePayload,
  type PrinterMachineSummary,
  type PrinterMachineToggleResult,
  type PrinterModelOption,
  updatePrinterMachineStatus,
} from "@/modules/printers/machines/machinesApi";
import { Alert, AlertDescription, AlertTitle } from "@/shared/ui/alert";
import { Button } from "@/shared/ui/button";
import {
  DropdownMenu,
  DropdownMenuCheckboxItem,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/shared/ui/dropdown-menu";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/shared/ui/table";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/shared/ui/tooltip";
import { cn } from "@/shared/lib/utils";

type ColumnKey = "status" | "machine" | "ip" | "manufacturer" | "model" | "sector" | "costCenter";
type SortKey = ColumnKey;
type SortDirection = "asc" | "desc";
type DropSide = "before" | "after";

interface ColumnPreferences {
  order: ColumnKey[];
  visible: ColumnKey[];
}

// -----------------------------------------------------------------------------
// 📌 PREFERÊNCIAS DE COLUNAS POR USUÁRIO
// -----------------------------------------------------------------------------
// Ordem e visibilidade são locais ao navegador e separadas pelo username.
// Preferências inválidas são descartadas para não quebrar novas versões.
const COLUMN_PREFERENCES_STORAGE_KEY = "sistema-erp-printer-machines-columns";

const DEFAULT_COLUMN_ORDER: ColumnKey[] = [
  "status",
  "machine",
  "ip",
  "manufacturer",
  "model",
  "sector",
  "costCenter",
];

const columnLabels: Record<ColumnKey, string> = {
  status: "Status",
  machine: "Máquina",
  ip: "IP",
  manufacturer: "Fabricante",
  model: "Modelo",
  sector: "Setor",
  costCenter: "Centro de custo",
};

export function MachinesPage() {
  return (
    <RequireAuth permission="can_access_printers_machines">
      <MachinesContent />
    </RequireAuth>
  );
}

function MachinesContent() {
  const { user } = useAuth();
  const [machines, setMachines] = useState<PrinterMachine[]>([]);
  const [summary, setSummary] = useState<PrinterMachineSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [togglingMachineId, setTogglingMachineId] = useState<number | null>(null);
  const [createDialogOpen, setCreateDialogOpen] = useState(false);
  const [detailsOpen, setDetailsOpen] = useState(false);
  const [selectedMachine, setSelectedMachine] = useState<PrinterMachine | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [createError, setCreateError] = useState<string | null>(null);
  const [createFieldErrors, setCreateFieldErrors] = useState<Record<string, string[]>>({});
  const [sortKey, setSortKey] = useState<SortKey | null>(null);
  const [sortDirection, setSortDirection] = useState<SortDirection>("asc");
  const [columnOrder, setColumnOrder] = useState<ColumnKey[]>(DEFAULT_COLUMN_ORDER);
  const [visibleColumns, setVisibleColumns] = useState<ColumnKey[]>(DEFAULT_COLUMN_ORDER);
  const [preferencesLoaded, setPreferencesLoaded] = useState(false);
  const [draggedColumn, setDraggedColumn] = useState<ColumnKey | null>(null);
  const [dragOverColumn, setDragOverColumn] = useState<ColumnKey | null>(null);
  const [dropSide, setDropSide] = useState<DropSide>("before");
  const [dragPosition, setDragPosition] = useState<{ x: number; y: number } | null>(null);
  const draggedColumnRef = useRef<ColumnKey | null>(null);
  const dragOverColumnRef = useRef<ColumnKey | null>(null);

  const machinePermissions = user?.permissoes.impressoras;
  const canCreate = Boolean(machinePermissions?.criar_maquinas);
  const canEdit = Boolean(machinePermissions?.editar_maquinas);
  const canToggle = Boolean(machinePermissions?.alternar_status_maquinas);
  const preferencesStorageKey = `${COLUMN_PREFERENCES_STORAGE_KEY}:${user?.username ?? "default"}`;

  const displayedColumns = useMemo(
    () => columnOrder.filter((column) => visibleColumns.includes(column)),
    [columnOrder, visibleColumns],
  );

  const displayedMachines = useMemo(() => {
    if (!sortKey) return machines;

    return [...machines].sort((current, next) => {
      const currentValue = getSortValue(current, sortKey);
      const nextValue = getSortValue(next, sortKey);
      const result = currentValue.localeCompare(nextValue, "pt-BR", {
        numeric: true,
        sensitivity: "base",
      });
      return sortDirection === "asc" ? result : -result;
    });
  }, [machines, sortDirection, sortKey]);

  const modelOptions = useMemo(() => collectModelOptions(machines), [machines]);

  async function loadMachines() {
    setLoading(true);
    setError(null);
    try {
      const [machineData, summaryData] = await Promise.all([
        fetchPrinterMachines(),
        fetchPrinterMachineSummary(),
      ]);
      setMachines(machineData);
      setSummary(summaryData);
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Não foi possível carregar as máquinas.",
      );
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadMachines();
  }, []);

  useEffect(() => {
    setPreferencesLoaded(false);
    setColumnOrder(DEFAULT_COLUMN_ORDER);
    setVisibleColumns(DEFAULT_COLUMN_ORDER);

    const storedPreferences = window.localStorage.getItem(preferencesStorageKey);
    if (storedPreferences) {
      try {
        const parsedPreferences = JSON.parse(storedPreferences);
        if (isValidColumnPreferences(parsedPreferences)) {
          setColumnOrder(parsedPreferences.order);
          setVisibleColumns(parsedPreferences.visible);
        } else {
          window.localStorage.removeItem(preferencesStorageKey);
        }
      } catch {
        window.localStorage.removeItem(preferencesStorageKey);
      }
    }

    setPreferencesLoaded(true);
  }, [preferencesStorageKey]);

  useEffect(() => {
    if (!preferencesLoaded) return;
    const preferences: ColumnPreferences = {
      order: columnOrder,
      visible: visibleColumns,
    };
    window.localStorage.setItem(preferencesStorageKey, JSON.stringify(preferences));
  }, [columnOrder, preferencesLoaded, preferencesStorageKey, visibleColumns]);

  function openCreateDialog() {
    setCreateError(null);
    setCreateFieldErrors({});
    setCreateDialogOpen(true);
  }

  function openDetails(machine: PrinterMachine) {
    setSelectedMachine(machine);
    setDetailsOpen(true);
  }

  async function createMachine(payload: PrinterMachinePayload) {
    setCreating(true);
    setCreateError(null);
    setCreateFieldErrors({});
    try {
      const createdMachine = await createPrinterMachine(payload);
      setMachines((current) => [...current, createdMachine]);
      setCreateDialogOpen(false);
      toast.success("Máquina cadastrada com sucesso.");

      try {
        setSummary(await fetchPrinterMachineSummary());
      } catch {
        setError("A máquina foi cadastrada, mas o resumo não pôde ser atualizado.");
        toast.error("Atualize a tela para recarregar os cards.");
      }
    } catch (requestError) {
      const apiError =
        requestError instanceof MachinesApiError
          ? requestError
          : new MachinesApiError(
              requestError instanceof Error
                ? requestError.message
                : "Não foi possível cadastrar a máquina.",
            );
      setCreateError(apiError.message);
      setCreateFieldErrors(apiError.fieldErrors);
      toast.error(apiError.message);
    } finally {
      setCreating(false);
    }
  }

  async function toggleStatus(machine: PrinterMachine) {
    setTogglingMachineId(machine.id);
    setError(null);
    try {
      const result = await updatePrinterMachineStatus(machine.id, !machine.is_active);
      applyToggleResult(result);
      toast.success(result.message);
    } catch (requestError) {
      const message =
        requestError instanceof Error
          ? requestError.message
          : "Não foi possível alterar o status da máquina.";
      setError(message);
      toast.error(message);
    } finally {
      setTogglingMachineId(null);
    }
  }

  function applyToggleResult(result: PrinterMachineToggleResult) {
    setMachines((current) => [
      ...current.filter((machine) => machine.id !== result.machine.id),
      result.machine,
    ]);
    setSummary(result.summary);
    setSortKey(null);
    setSelectedMachine((current) => (current?.id === result.machine.id ? result.machine : current));
  }

  function applyMachineUpdate(updatedMachine: PrinterMachine) {
    setMachines((current) =>
      current.map((machine) => (machine.id === updatedMachine.id ? updatedMachine : machine)),
    );
    setSelectedMachine((current) => (current?.id === updatedMachine.id ? updatedMachine : current));
  }

  function handleSort(nextKey: SortKey) {
    if (nextKey === sortKey) {
      setSortDirection((current) => (current === "asc" ? "desc" : "asc"));
      return;
    }
    setSortKey(nextKey);
    setSortDirection("asc");
  }

  function toggleColumnVisibility(column: ColumnKey, checked: boolean) {
    if (!checked && visibleColumns.length === 1) {
      toast.error("Mantenha pelo menos uma coluna visível.");
      return;
    }
    setVisibleColumns((current) =>
      checked
        ? columnOrder.filter((candidate) => candidate === column || current.includes(candidate))
        : current.filter((candidate) => candidate !== column),
    );
  }

  function restoreDefaultColumns() {
    setColumnOrder(DEFAULT_COLUMN_ORDER);
    setVisibleColumns(DEFAULT_COLUMN_ORDER);
    toast.success("Colunas restauradas para o padrão.");
  }

  // ---------------------------------------------------------------------------
  // 📌 REORDENAÇÃO COMPATÍVEL COM MOUSE E TOQUE
  // ---------------------------------------------------------------------------
  // Pointer Events e pointer capture mantêm o arraste funcional também em
  // dispositivos móveis, sem depender da API HTML5 de drag and drop.
  function handleColumnPointerDown(event: PointerEvent<HTMLSpanElement>, column: ColumnKey) {
    if (event.button !== 0) return;
    event.preventDefault();
    event.currentTarget.setPointerCapture(event.pointerId);
    draggedColumnRef.current = column;
    setDraggedColumn(column);
    setDragOverColumn(column);
    setDragPosition({ x: event.clientX, y: event.clientY });
  }

  function handleColumnPointerMove(event: PointerEvent<HTMLSpanElement>) {
    if (!draggedColumnRef.current) return;
    const target = document
      .elementFromPoint(event.clientX, event.clientY)
      ?.closest<HTMLElement>("[data-machine-column-key]");
    const targetColumn = target?.dataset.machineColumnKey as ColumnKey | undefined;
    if (!targetColumn || !DEFAULT_COLUMN_ORDER.includes(targetColumn)) return;
    const bounds = target?.getBoundingClientRect();
    dragOverColumnRef.current = targetColumn;
    setDragOverColumn(targetColumn);
    setDropSide(bounds && event.clientX > bounds.left + bounds.width / 2 ? "after" : "before");
    setDragPosition({ x: event.clientX, y: event.clientY });
  }

  function handleColumnPointerUp(event: PointerEvent<HTMLSpanElement>) {
    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId);
    }

    const sourceColumn = draggedColumnRef.current;
    const targetColumn = dragOverColumnRef.current;
    if (sourceColumn && targetColumn && sourceColumn !== targetColumn) {
      setColumnOrder((current) => {
        const nextOrder = current.filter((column) => column !== sourceColumn);
        const targetIndex = nextOrder.indexOf(targetColumn);
        nextOrder.splice(targetIndex + (dropSide === "after" ? 1 : 0), 0, sourceColumn);
        return nextOrder;
      });
    }
    clearColumnDrag();
  }

  function clearColumnDrag() {
    draggedColumnRef.current = null;
    dragOverColumnRef.current = null;
    setDraggedColumn(null);
    setDragOverColumn(null);
    setDropSide("before");
    setDragPosition(null);
  }

  return (
    <div className="mx-auto flex max-w-[1540px] flex-col gap-4">
      <MachinesSummaryCards summary={summary} loading={loading} />

      {error && (
        <Alert variant="destructive">
          <AlertTitle>Erro na tela de máquinas</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      <section className="overflow-hidden rounded-lg border border-border/70 bg-card shadow-[var(--shadow-card)]">
        <div className="flex min-h-14 items-center justify-between gap-3 border-b border-border/70 px-3 py-2.5 sm:px-4">
          <div>
            {canCreate && (
              <Button type="button" onClick={openCreateDialog}>
                <Plus className="h-4 w-4" />
                Adicionar máquina
              </Button>
            )}
          </div>

          <TooltipProvider>
            <DropdownMenu>
              <Tooltip>
                <TooltipTrigger asChild>
                  <DropdownMenuTrigger asChild>
                    <Button
                      type="button"
                      variant="outline"
                      size="icon"
                      aria-label="Selecionar colunas da tabela"
                    >
                      <Columns3 className="h-4 w-4" />
                    </Button>
                  </DropdownMenuTrigger>
                </TooltipTrigger>
                <TooltipContent>Selecionar colunas</TooltipContent>
              </Tooltip>
              <DropdownMenuContent align="end" className="w-56">
                <DropdownMenuLabel>Colunas visíveis</DropdownMenuLabel>
                <DropdownMenuSeparator />
                {columnOrder.map((column) => (
                  <DropdownMenuCheckboxItem
                    key={column}
                    checked={visibleColumns.includes(column)}
                    onCheckedChange={(checked) => toggleColumnVisibility(column, checked === true)}
                    onSelect={(event) => event.preventDefault()}
                  >
                    {columnLabels[column]}
                  </DropdownMenuCheckboxItem>
                ))}
                <DropdownMenuSeparator />
                <DropdownMenuItem onSelect={restoreDefaultColumns}>
                  <RotateCcw className="h-4 w-4" />
                  Restaurar padrão
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </TooltipProvider>
        </div>

        {loading ? (
          <div className="flex min-h-64 items-center justify-center text-sm text-muted-foreground">
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            Carregando máquinas...
          </div>
        ) : displayedMachines.length === 0 ? (
          <div className="flex min-h-64 flex-col items-center justify-center px-6 text-center">
            <Printer className="h-9 w-9 text-muted-foreground" />
            <h2 className="mt-4 text-base font-semibold">Nenhuma máquina cadastrada</h2>
            <p className="mt-2 max-w-md text-sm text-muted-foreground">
              Use o botão Adicionar máquina para iniciar o inventário.
            </p>
          </div>
        ) : (
          <div className="max-w-full touch-pan-x overflow-x-auto overscroll-x-contain p-2 sm:p-3">
            <Table className="min-w-[980px]">
              <TableHeader>
                <TableRow>
                  {displayedColumns.map((column) => (
                    <TableHead
                      key={column}
                      data-machine-column-key={column}
                      aria-sort={
                        sortKey === column
                          ? sortDirection === "asc"
                            ? "ascending"
                            : "descending"
                          : "none"
                      }
                      className={cn(
                        "relative select-none transition-[background-color,box-shadow,color,opacity] duration-150",
                        draggedColumn === column &&
                          "bg-primary/12 text-foreground opacity-80 shadow-[inset_0_0_0_1px_color-mix(in_oklab,var(--primary)_38%,transparent)]",
                        dragOverColumn === column && draggedColumn !== column && "bg-primary/8",
                        dragOverColumn === column &&
                          draggedColumn !== column &&
                          dropSide === "before" &&
                          "before:absolute before:inset-y-1 before:left-0 before:w-0.5 before:rounded-full before:bg-primary",
                        dragOverColumn === column &&
                          draggedColumn !== column &&
                          dropSide === "after" &&
                          "after:absolute after:inset-y-1 after:right-0 after:w-0.5 after:rounded-full after:bg-primary",
                      )}
                    >
                      <span className="inline-flex items-center gap-1">
                        <span
                          className={cn(
                            "inline-flex touch-none items-center rounded-sm p-1 text-muted-foreground/70 transition-colors hover:bg-primary/10 hover:text-foreground",
                            draggedColumn === column ? "cursor-grabbing" : "cursor-grab",
                          )}
                          title="Arraste para mudar a posição da coluna"
                          onPointerDown={(event) => handleColumnPointerDown(event, column)}
                          onPointerMove={handleColumnPointerMove}
                          onPointerUp={handleColumnPointerUp}
                          onPointerCancel={clearColumnDrag}
                        >
                          <GripVertical
                            className="h-3.5 w-3.5 text-muted-foreground/70"
                            aria-hidden="true"
                          />
                        </span>
                        <button
                          type="button"
                          onClick={() => handleSort(column)}
                          className="inline-flex h-8 items-center gap-1.5 rounded-sm px-1 text-left font-medium text-muted-foreground transition-colors hover:bg-primary/10 hover:text-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring dark:hover:bg-primary/20"
                        >
                          {columnLabels[column]}
                          <SortIcon active={sortKey === column} direction={sortDirection} />
                        </button>
                      </span>
                    </TableHead>
                  ))}
                </TableRow>
              </TableHeader>
              <TableBody>
                {displayedMachines.map((machine) => (
                  <TableRow
                    key={machine.id}
                    tabIndex={0}
                    role="button"
                    aria-label={`Abrir detalhes de ${machine.name}`}
                    className="cursor-pointer transition-colors hover:bg-primary/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring dark:hover:bg-primary/20"
                    onClick={() => openDetails(machine)}
                    onKeyDown={(event) => {
                      if (event.key === "Enter" || event.key === " ") {
                        event.preventDefault();
                        openDetails(machine);
                      }
                    }}
                  >
                    {displayedColumns.map((column) =>
                      renderMachineCell({
                        machine,
                        column,
                        canToggle,
                        toggling: togglingMachineId === machine.id,
                        onToggle: toggleStatus,
                      }),
                    )}
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}
      </section>

      <MachineFormDialog
        open={createDialogOpen}
        machine={null}
        saving={creating}
        error={createError}
        fieldErrors={createFieldErrors}
        onOpenChange={setCreateDialogOpen}
        onSubmit={createMachine}
      />

      <MachineDetailsDialog
        machine={selectedMachine}
        open={detailsOpen}
        modelOptions={modelOptions}
        canEdit={canEdit}
        canToggle={canToggle}
        onOpenChange={setDetailsOpen}
        onMachineUpdated={applyMachineUpdate}
        onMachineToggled={applyToggleResult}
      />

      <ColumnDragPreview
        label={draggedColumn ? columnLabels[draggedColumn] : null}
        position={dragPosition}
      />
    </div>
  );
}

function renderMachineCell({
  machine,
  column,
  canToggle,
  toggling,
  onToggle,
}: {
  machine: PrinterMachine;
  column: ColumnKey;
  canToggle: boolean;
  toggling: boolean;
  onToggle: (machine: PrinterMachine) => Promise<void>;
}) {
  switch (column) {
    case "status":
      return (
        <TableCell key={column} className="text-center">
          {canToggle ? (
            <Button
              type="button"
              size="sm"
              variant="outline"
              aria-label={machine.is_active ? `Inativar ${machine.name}` : `Ativar ${machine.name}`}
              className={cn(
                "min-w-24",
                machine.is_active
                  ? "border-emerald-500/40 bg-emerald-500/12 text-emerald-700 hover:bg-emerald-500/20 dark:text-emerald-300"
                  : "border-red-500/40 bg-red-500/12 text-red-700 hover:bg-red-500/20 dark:text-red-300",
              )}
              onClick={(event) => {
                event.stopPropagation();
                void onToggle(machine);
              }}
              onKeyDown={(event) => event.stopPropagation()}
              disabled={toggling}
            >
              {toggling ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : machine.is_active ? (
                <Power className="h-4 w-4" />
              ) : (
                <PowerOff className="h-4 w-4" />
              )}
              {machine.is_active ? "Ativa" : "Inativa"}
            </Button>
          ) : (
            <span
              className={cn(
                "inline-flex min-w-20 items-center justify-center rounded-md border px-2.5 py-1 text-xs font-semibold",
                machine.is_active
                  ? "border-emerald-500/35 bg-emerald-500/12 text-emerald-700 dark:text-emerald-300"
                  : "border-red-500/35 bg-red-500/12 text-red-700 dark:text-red-300",
              )}
            >
              {machine.is_active ? "Ativa" : "Inativa"}
            </span>
          )}
        </TableCell>
      );
    case "machine":
      return (
        <TableCell key={column} className="font-medium">
          {machine.name}
        </TableCell>
      );
    case "ip":
      return <TableCell key={column}>{machine.ip_address}</TableCell>;
    case "manufacturer":
      return <TableCell key={column}>{machine.manufacturer ?? "-"}</TableCell>;
    case "model":
      return <TableCell key={column}>{machine.model ?? "-"}</TableCell>;
    case "sector":
      return <TableCell key={column}>{machine.sector ?? "-"}</TableCell>;
    case "costCenter":
      return <TableCell key={column}>{machine.cost_center ?? "-"}</TableCell>;
  }
}

function SortIcon({ active, direction }: { active: boolean; direction: SortDirection }) {
  if (!active) return <ChevronsUpDown className="h-3.5 w-3.5" />;
  return direction === "asc" ? (
    <ArrowDownAZ className="h-3.5 w-3.5" />
  ) : (
    <ArrowUpAZ className="h-3.5 w-3.5" />
  );
}

function getSortValue(machine: PrinterMachine, key: SortKey) {
  switch (key) {
    case "status":
      return machine.is_active ? "Ativa" : "Inativa";
    case "machine":
      return machine.name;
    case "ip":
      return machine.ip_address;
    case "manufacturer":
      return machine.manufacturer ?? "";
    case "model":
      return machine.model ?? "";
    case "sector":
      return machine.sector ?? "";
    case "costCenter":
      return machine.cost_center ?? "";
  }
}

function collectModelOptions(machines: PrinterMachine[]): PrinterModelOption[] {
  const options = new Map<number, PrinterModelOption>();
  for (const machine of machines) {
    if (!machine.model_id || !machine.manufacturer || !machine.model) continue;
    options.set(machine.model_id, {
      id: machine.model_id,
      manufacturer: machine.manufacturer,
      model: machine.model,
      type: machine.type,
      color_mode: machine.color_mode,
      image_url: machine.image_url,
    });
  }
  return [...options.values()].sort(
    (current, next) =>
      current.manufacturer.localeCompare(next.manufacturer, "pt-BR", {
        sensitivity: "base",
      }) ||
      current.model.localeCompare(next.model, "pt-BR", {
        sensitivity: "base",
      }),
  );
}

function isValidColumnPreferences(value: unknown): value is ColumnPreferences {
  if (!value || typeof value !== "object") return false;
  const preferences = value as Partial<ColumnPreferences>;
  return (
    isCompleteColumnOrder(preferences.order) &&
    Array.isArray(preferences.visible) &&
    preferences.visible.length > 0 &&
    preferences.visible.every(
      (column): column is ColumnKey =>
        typeof column === "string" && DEFAULT_COLUMN_ORDER.includes(column as ColumnKey),
    ) &&
    new Set(preferences.visible).size === preferences.visible.length
  );
}

function isCompleteColumnOrder(value: unknown): value is ColumnKey[] {
  return (
    Array.isArray(value) &&
    value.length === DEFAULT_COLUMN_ORDER.length &&
    DEFAULT_COLUMN_ORDER.every((column) => value.includes(column))
  );
}
