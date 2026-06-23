import { useEffect, useMemo, useRef, useState, type PointerEvent } from "react";
import { Activity, Columns3, GripVertical, Loader2, RotateCcw } from "lucide-react";
import { toast } from "sonner";

import { RequireAuth } from "@/modules/auth/RequireAuth";
import { useAuth } from "@/modules/auth/authStore";
import { ColumnDragPreview } from "@/modules/printers/shared/ColumnDragPreview";
import { StatusDetailsDialog } from "@/modules/printers/status/components/StatusDetailsDialog";
import { StatusSummaryCards } from "@/modules/printers/status/components/StatusSummaryCards";
import {
  fetchPrinterStatuses,
  fetchPrinterStatusSummary,
  type AlertLevel,
  type OperationalStatus,
  type PrinterOperationalStatus,
  type PrinterStatusSummary,
} from "@/modules/printers/status/statusApi";
import { Alert, AlertDescription, AlertTitle } from "@/shared/ui/alert";
import { Badge } from "@/shared/ui/badge";
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

const statusLabels: Record<OperationalStatus, string> = {
  online: "Online",
  offline: "Offline",
};

const statusStyles: Record<OperationalStatus, string> = {
  online: "border-emerald-500/30 bg-emerald-500/12 text-emerald-700 dark:text-emerald-300",
  offline: "border-red-500/30 bg-red-500/12 text-red-700 dark:text-red-300",
};

const alertPriority: Record<AlertLevel, number> = {
  vermelho: 0,
  amarelo: 1,
  cinza: 2,
  verde: 3,
};

const alertLabels: Record<AlertLevel, string> = {
  cinza: "Desconhecido",
  verde: "Normal",
  amarelo: "Atenção",
  vermelho: "Crítico",
};

const alertDotStyles: Record<AlertLevel, string> = {
  cinza: "bg-muted-foreground",
  verde: "bg-emerald-500",
  amarelo: "bg-amber-400",
  vermelho: "bg-red-500",
};

const alertRowStyles: Record<AlertLevel, string> = {
  cinza: "border-l-4 border-l-muted-foreground/50 hover:bg-muted/65",
  verde: "border-l-4 border-l-emerald-500/60 hover:bg-emerald-500/8",
  amarelo: "border-l-4 border-l-amber-400 bg-amber-500/[0.035] hover:bg-amber-500/10",
  vermelho: "border-l-4 border-l-red-500 bg-red-500/[0.045] hover:bg-red-500/12",
};

type ColumnKey = "status" | "alert" | "message" | "location" | "machine" | "ip" | "updatedAt";
type DropSide = "before" | "after";

interface ColumnPreferences {
  order: ColumnKey[];
  visible: ColumnKey[];
}

// -----------------------------------------------------------------------------
// 📌 PREFERÊNCIAS DA CENTRAL OPERACIONAL
// -----------------------------------------------------------------------------
// Cada usuário organiza a própria tabela sem alterar o contrato ou a ordenação
// dos demais usuários. Dados incompatíveis são removidos no carregamento.
const COLUMN_PREFERENCES_STORAGE_KEY = "sistema-erp-printer-status-columns";

const DEFAULT_COLUMN_ORDER: ColumnKey[] = [
  "status",
  "alert",
  "message",
  "location",
  "machine",
  "ip",
  "updatedAt",
];

const columnLabels: Record<ColumnKey, string> = {
  status: "Status",
  alert: "Alerta",
  message: "Mensagem",
  location: "Local",
  machine: "Máquina",
  ip: "IP",
  updatedAt: "Atualizado em",
};

export function StatusPage() {
  return (
    <RequireAuth permission="can_access_printers_status">
      <StatusContent />
    </RequireAuth>
  );
}

function StatusContent() {
  const { user } = useAuth();
  const [statuses, setStatuses] = useState<PrinterOperationalStatus[]>([]);
  const [summary, setSummary] = useState<PrinterStatusSummary | null>(null);
  const [selectedStatus, setSelectedStatus] = useState<PrinterOperationalStatus | null>(null);
  const [detailsOpen, setDetailsOpen] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [columnOrder, setColumnOrder] = useState<ColumnKey[]>(DEFAULT_COLUMN_ORDER);
  const [visibleColumns, setVisibleColumns] = useState<ColumnKey[]>(DEFAULT_COLUMN_ORDER);
  const [columnPreferencesLoaded, setColumnPreferencesLoaded] = useState(false);
  const [draggedColumn, setDraggedColumn] = useState<ColumnKey | null>(null);
  const [dragOverColumn, setDragOverColumn] = useState<ColumnKey | null>(null);
  const [dropSide, setDropSide] = useState<DropSide>("before");
  const [dragPosition, setDragPosition] = useState<{ x: number; y: number } | null>(null);
  const draggedColumnRef = useRef<ColumnKey | null>(null);
  const dragOverColumnRef = useRef<ColumnKey | null>(null);
  const columnPreferencesStorageKey = `${COLUMN_PREFERENCES_STORAGE_KEY}:${user?.username ?? "default"}`;

  const displayedColumns = useMemo(
    () => columnOrder.filter((column) => visibleColumns.includes(column)),
    [columnOrder, visibleColumns],
  );

  const sortedStatuses = useMemo(
    // Alertas críticos permanecem no topo independentemente da ordem recebida.
    () =>
      [...statuses].sort(
        (current, next) =>
          alertPriority[current.nivel_alerta] - alertPriority[next.nivel_alerta] ||
          current.machine_name.localeCompare(next.machine_name, "pt-BR", { sensitivity: "base" }),
      ),
    [statuses],
  );

  async function loadStatuses() {
    setLoading(true);
    setError(null);
    try {
      const [statusData, summaryData] = await Promise.all([
        fetchPrinterStatuses(),
        fetchPrinterStatusSummary(),
      ]);
      setStatuses(statusData);
      setSummary(summaryData);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Nao foi possivel carregar os status.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadStatuses();
  }, []);

  useEffect(() => {
    setColumnPreferencesLoaded(false);
    setColumnOrder(DEFAULT_COLUMN_ORDER);
    setVisibleColumns(DEFAULT_COLUMN_ORDER);
    const storedPreferences = window.localStorage.getItem(columnPreferencesStorageKey);

    if (storedPreferences) {
      try {
        const parsedPreferences = JSON.parse(storedPreferences);
        if (isValidColumnPreferences(parsedPreferences)) {
          setColumnOrder(parsedPreferences.order);
          setVisibleColumns(parsedPreferences.visible);
        } else {
          window.localStorage.removeItem(columnPreferencesStorageKey);
        }
      } catch {
        window.localStorage.removeItem(columnPreferencesStorageKey);
      }
    }

    setColumnPreferencesLoaded(true);
  }, [columnPreferencesStorageKey]);

  useEffect(() => {
    if (!columnPreferencesLoaded) return;
    const preferences: ColumnPreferences = {
      order: columnOrder,
      visible: visibleColumns,
    };
    window.localStorage.setItem(columnPreferencesStorageKey, JSON.stringify(preferences));
  }, [columnOrder, columnPreferencesLoaded, columnPreferencesStorageKey, visibleColumns]);

  function openDetails(status: PrinterOperationalStatus) {
    setSelectedStatus(status);
    setDetailsOpen(true);
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
      ?.closest<HTMLElement>("[data-column-key]");
    const targetColumn = target?.dataset.columnKey as ColumnKey | undefined;
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
      setColumnOrder((currentOrder) => {
        const nextOrder = currentOrder.filter((column) => column !== sourceColumn);
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
      <StatusSummaryCards summary={summary} loading={loading} />

      {error && (
        <Alert variant="destructive">
          <AlertTitle>Erro ao consultar status</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      <section className="overflow-hidden rounded-lg border border-border/70 bg-card shadow-[var(--shadow-card)]">
        <div className="flex min-h-14 items-center justify-end border-b border-border/70 px-3 py-2.5 sm:px-4">
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
            Carregando status...
          </div>
        ) : sortedStatuses.length === 0 ? (
          <div className="flex min-h-64 flex-col items-center justify-center px-6 text-center">
            <Activity className="h-9 w-9 text-muted-foreground" />
            <h2 className="mt-4 text-base font-semibold">Nenhum status disponível</h2>
            <p className="mt-2 max-w-md text-sm text-muted-foreground">
              Os estados operacionais aparecerão aqui quando houver impressoras cadastradas.
            </p>
          </div>
        ) : (
          <div className="max-w-full touch-pan-x overflow-x-auto overscroll-x-contain p-2 sm:p-3">
            <Table className="min-w-[1180px]">
              <TableHeader>
                <TableRow>
                  {displayedColumns.map((column) => (
                    <TableHead
                      key={column}
                      data-column-key={column}
                      aria-label={`${columnLabels[column]}. Arraste para mudar a posição da coluna.`}
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
                      <span
                        className={cn(
                          "inline-flex touch-none items-center gap-1.5 rounded-sm px-1 py-1 transition-colors hover:bg-primary/10 hover:text-foreground",
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
                        {columnLabels[column]}
                      </span>
                    </TableHead>
                  ))}
                </TableRow>
              </TableHeader>
              <TableBody>
                {sortedStatuses.map((status) => (
                  <TableRow
                    key={status.machine_id}
                    tabIndex={0}
                    role="button"
                    aria-label={`Abrir detalhes de ${status.machine_name}`}
                    className={cn(
                      "cursor-pointer transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring",
                      alertRowStyles[status.nivel_alerta],
                    )}
                    onClick={() => openDetails(status)}
                    onKeyDown={(event) => {
                      if (event.key === "Enter" || event.key === " ") {
                        event.preventDefault();
                        openDetails(status);
                      }
                    }}
                  >
                    {displayedColumns.map((column) => renderStatusCell(status, column))}
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}
      </section>

      <StatusDetailsDialog
        status={selectedStatus}
        open={detailsOpen}
        onOpenChange={setDetailsOpen}
      />

      <ColumnDragPreview
        label={draggedColumn ? columnLabels[draggedColumn] : null}
        position={dragPosition}
      />
    </div>
  );
}

function renderStatusCell(status: PrinterOperationalStatus, column: ColumnKey) {
  switch (column) {
    case "status":
      return (
        <TableCell key={column}>
          <Badge variant="outline" className={statusStyles[status.status_operacional]}>
            {statusLabels[status.status_operacional]}
          </Badge>
        </TableCell>
      );
    case "alert":
      return (
        <TableCell key={column}>
          <span className="inline-flex items-center gap-2">
            <span
              className={cn(
                "h-2.5 w-2.5 shrink-0 rounded-full",
                alertDotStyles[status.nivel_alerta],
              )}
              aria-hidden="true"
            />
            <span>{alertLabels[status.nivel_alerta]}</span>
          </span>
        </TableCell>
      );
    case "message":
      return (
        <TableCell key={column} className="max-w-[300px] whitespace-normal">
          {status.mensagem_alerta ?? "Sem alerta informado"}
        </TableCell>
      );
    case "location":
      return <TableCell key={column}>{status.sector ?? "-"}</TableCell>;
    case "machine":
      return (
        <TableCell key={column} className="font-medium">
          {status.machine_name}
        </TableCell>
      );
    case "ip":
      return <TableCell key={column}>{status.ip_address}</TableCell>;
    case "updatedAt":
      return (
        <TableCell key={column}>{formatRelativeUpdate(status.ultima_verificacao_em)}</TableCell>
      );
  }
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

function formatRelativeUpdate(value: string | null) {
  if (!value) return "Desatualizado";

  const elapsedMs = Date.now() - new Date(value).getTime();
  const elapsedMinutes = Math.max(0, Math.floor(elapsedMs / 60_000));

  if (elapsedMinutes < 1) return "Agora";
  if (elapsedMinutes < 60) return `Há ${elapsedMinutes} min`;

  const elapsedHours = Math.floor(elapsedMinutes / 60);
  if (elapsedHours < 24) return `Há ${elapsedHours} h`;

  return "Desatualizado";
}
