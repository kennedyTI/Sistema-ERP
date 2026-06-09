import { useEffect, useMemo, useRef, useState, type PointerEvent } from "react";
import { Activity, GripVertical, Loader2, RefreshCw } from "lucide-react";

import { RequireAuth } from "@/modules/auth/RequireAuth";
import { useAuth } from "@/modules/auth/authStore";
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
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/shared/ui/table";
import { cn } from "@/shared/lib/utils";

const statusLabels: Record<OperationalStatus, string> = {
  desconhecido: "Desconhecido",
  online: "Online",
  offline: "Offline",
  erro: "Erro",
};

const statusStyles: Record<OperationalStatus, string> = {
  desconhecido: "border-muted-foreground/30 bg-muted text-muted-foreground",
  online: "border-emerald-500/30 bg-emerald-500/12 text-emerald-700 dark:text-emerald-300",
  offline: "border-red-500/30 bg-red-500/12 text-red-700 dark:text-red-300",
  erro: "border-orange-500/30 bg-orange-500/12 text-orange-700 dark:text-orange-300",
};

const alertPriority: Record<AlertLevel, number> = {
  vermelho: 0,
  amarelo: 1,
  cinza: 2,
  verde: 3,
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

const COLUMN_ORDER_STORAGE_KEY = "sistema-erp-printer-status-column-order";

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
  const [columnPreferencesLoaded, setColumnPreferencesLoaded] = useState(false);
  const [draggedColumn, setDraggedColumn] = useState<ColumnKey | null>(null);
  const [dragOverColumn, setDragOverColumn] = useState<ColumnKey | null>(null);
  const draggedColumnRef = useRef<ColumnKey | null>(null);
  const dragOverColumnRef = useRef<ColumnKey | null>(null);
  const columnOrderStorageKey = `${COLUMN_ORDER_STORAGE_KEY}:${user?.username ?? "default"}`;

  const sortedStatuses = useMemo(
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
    const storedOrder = window.localStorage.getItem(columnOrderStorageKey);

    if (storedOrder) {
      try {
        const parsedOrder = JSON.parse(storedOrder);
        if (isValidColumnOrder(parsedOrder)) setColumnOrder(parsedOrder);
      } catch {
        window.localStorage.removeItem(columnOrderStorageKey);
      }
    }

    setColumnPreferencesLoaded(true);
  }, [columnOrderStorageKey]);

  useEffect(() => {
    if (!columnPreferencesLoaded) return;
    window.localStorage.setItem(columnOrderStorageKey, JSON.stringify(columnOrder));
  }, [columnOrder, columnOrderStorageKey, columnPreferencesLoaded]);

  function openDetails(status: PrinterOperationalStatus) {
    setSelectedStatus(status);
    setDetailsOpen(true);
  }

  function handleColumnPointerDown(event: PointerEvent<HTMLSpanElement>, column: ColumnKey) {
    if (event.button !== 0) return;

    event.preventDefault();
    event.currentTarget.setPointerCapture(event.pointerId);
    draggedColumnRef.current = column;
    setDraggedColumn(column);
  }

  function handleColumnPointerMove(event: PointerEvent<HTMLSpanElement>) {
    if (!draggedColumnRef.current) return;

    const target = document.elementFromPoint(event.clientX, event.clientY)?.closest<HTMLElement>(
      "[data-column-key]",
    );
    const targetColumn = target?.dataset.columnKey as ColumnKey | undefined;
    if (!targetColumn || !DEFAULT_COLUMN_ORDER.includes(targetColumn)) return;

    dragOverColumnRef.current = targetColumn;
    setDragOverColumn(targetColumn);
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
        nextOrder.splice(targetIndex, 0, sourceColumn);
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
  }

  return (
    <div className="mx-auto flex max-w-[1480px] flex-col gap-5">
      <section className="rounded-lg border border-border/70 bg-card px-6 py-6 shadow-[var(--shadow-card)]">
        <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
          <div>
            <p className="text-xs font-medium uppercase tracking-wide text-primary">Impressoras</p>
            <h1 className="mt-2 text-2xl font-semibold tracking-tight">Status</h1>
            <p className="mt-2 max-w-2xl text-sm text-muted-foreground">
              Central de consulta do estado atual e das orientações operacionais.
            </p>
          </div>
          <Button type="button" variant="outline" onClick={loadStatuses} disabled={loading}>
            {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
            Atualizar
          </Button>
        </div>
      </section>

      <StatusSummaryCards summary={summary} loading={loading} />

      {error && (
        <Alert variant="destructive">
          <AlertTitle>Erro ao consultar status</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      <section className="overflow-hidden rounded-lg border border-border/70 bg-card shadow-[var(--shadow-card)]">
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
          <div className="overflow-x-auto p-4">
            <Table className="min-w-[1180px]">
              <TableHeader>
                <TableRow>
                  {columnOrder.map((column) => (
                    <TableHead
                      key={column}
                      data-column-key={column}
                      aria-label={`${columnLabels[column]}. Arraste para mudar a posição da coluna.`}
                      className={cn(
                        "select-none transition-colors",
                        draggedColumn === column && "opacity-40",
                        dragOverColumn === column && draggedColumn !== column && "bg-primary/10",
                      )}
                    >
                      <span
                        className="inline-flex touch-none cursor-grab items-center gap-1.5 active:cursor-grabbing"
                        title="Arraste para mudar a posição da coluna"
                        onPointerDown={(event) => handleColumnPointerDown(event, column)}
                        onPointerMove={handleColumnPointerMove}
                        onPointerUp={handleColumnPointerUp}
                        onPointerCancel={clearColumnDrag}
                      >
                        <GripVertical className="h-3.5 w-3.5 text-muted-foreground/70" aria-hidden="true" />
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
                    {columnOrder.map((column) => renderStatusCell(status, column))}
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
        <TableCell key={column} className="max-w-[260px] whitespace-normal">
          <span className="inline-flex items-start gap-2">
            <span
              className={cn("mt-1.5 h-2.5 w-2.5 shrink-0 rounded-full", alertDotStyles[status.nivel_alerta])}
              aria-hidden="true"
            />
            <span>{status.mensagem_alerta ?? "-"}</span>
          </span>
        </TableCell>
      );
    case "message":
      return (
        <TableCell key={column} className="max-w-[300px] whitespace-normal">
          {status.mensagem_operador}
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
      return <TableCell key={column}>{formatRelativeUpdate(status.ultima_verificacao_em)}</TableCell>;
  }
}

function isValidColumnOrder(value: unknown): value is ColumnKey[] {
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
