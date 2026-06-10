import { useEffect, useMemo, useState } from "react";
import {
  ArrowDownAZ,
  ArrowUpAZ,
  ChevronsUpDown,
  Edit,
  Loader2,
  Plus,
  Power,
  PowerOff,
  RefreshCw,
} from "lucide-react";

import { RequireAuth } from "@/modules/auth/RequireAuth";
import { useAuth } from "@/modules/auth/authStore";
import { MachineFormDialog } from "@/modules/printers/machines/components/MachineFormDialog";
import {
  createPrinterMachine,
  fetchPrinterMachines,
  type PrinterMachine,
  type PrinterMachinePayload,
  updatePrinterMachine,
  updatePrinterMachineStatus,
} from "@/modules/printers/machines/machinesApi";
import { Alert, AlertDescription, AlertTitle } from "@/shared/ui/alert";
import { Badge } from "@/shared/ui/badge";
import { Button } from "@/shared/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/shared/ui/table";

type SortKey = "name" | "ip_address" | "manufacturer" | "model" | "sector" | "is_active";
type SortDirection = "asc" | "desc";

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
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [selectedMachine, setSelectedMachine] = useState<PrinterMachine | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [sortKey, setSortKey] = useState<SortKey>("name");
  const [sortDirection, setSortDirection] = useState<SortDirection>("asc");
  const machinePermissions = user?.permissoes.impressoras;
  const canCreate = Boolean(machinePermissions?.criar_maquinas);
  const canEdit = Boolean(machinePermissions?.editar_maquinas);
  const canToggle = Boolean(machinePermissions?.alternar_status_maquinas);

  const activeCount = useMemo(() => machines.filter((machine) => machine.is_active).length, [machines]);
  const sortedMachines = useMemo(() => {
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

  function handleSort(nextKey: SortKey) {
    if (nextKey === sortKey) {
      setSortDirection((current) => (current === "asc" ? "desc" : "asc"));
      return;
    }

    setSortKey(nextKey);
    setSortDirection("asc");
  }

  async function loadMachines() {
    setLoading(true);
    setError(null);
    try {
      setMachines(await fetchPrinterMachines());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Nao foi possivel carregar as maquinas.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadMachines();
  }, []);

  function openCreateDialog() {
    setSelectedMachine(null);
    setFormError(null);
    setDialogOpen(true);
  }

  function openEditDialog(machine: PrinterMachine) {
    setSelectedMachine(machine);
    setFormError(null);
    setDialogOpen(true);
  }

  async function handleSubmit(payload: PrinterMachinePayload) {
    setSaving(true);
    setFormError(null);
    try {
      if (selectedMachine) {
        await updatePrinterMachine(selectedMachine, payload);
      } else {
        await createPrinterMachine(payload);
      }
      setDialogOpen(false);
      await loadMachines();
    } catch (err) {
      setFormError(err instanceof Error ? err.message : "Nao foi possivel salvar a maquina.");
    } finally {
      setSaving(false);
    }
  }

  async function toggleStatus(machine: PrinterMachine) {
    setError(null);
    try {
      await updatePrinterMachineStatus(machine.id, !machine.is_active);
      await loadMachines();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Nao foi possivel alterar o status da maquina.");
    }
  }

  return (
    <div className="mx-auto flex max-w-[1180px] flex-col gap-5">
      <section className="rounded-lg border border-border/70 bg-card px-6 py-6 shadow-[var(--shadow-card)]">
        <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
          <div>
            <p className="text-xs font-medium uppercase tracking-wide text-primary">Impressoras</p>
            <h1 className="mt-2 text-2xl font-semibold tracking-tight">Maquinas</h1>
            <p className="mt-2 max-w-2xl text-sm text-muted-foreground">
              Cadastro inicial de maquinas do modulo Impressoras.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Button type="button" variant="outline" onClick={loadMachines} disabled={loading}>
              {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
              Atualizar
            </Button>
            {canCreate && (
              <Button type="button" onClick={openCreateDialog}>
                <Plus className="h-4 w-4" />
                Adicionar maquina
              </Button>
            )}
          </div>
        </div>

        <div className="mt-5 flex flex-wrap gap-2 text-sm">
          <Badge variant="secondary">{machines.length} cadastrada(s)</Badge>
          <Badge variant="outline">{activeCount} ativa(s)</Badge>
        </div>
      </section>

      {error && (
        <Alert variant="destructive">
          <AlertTitle>Erro</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      <section className="rounded-lg border border-border/70 bg-card p-4 shadow-[var(--shadow-card)]">
        {loading ? (
          <div className="flex min-h-56 items-center justify-center text-sm text-muted-foreground">
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            Carregando maquinas...
          </div>
        ) : machines.length === 0 ? (
          <div className="flex min-h-56 flex-col items-center justify-center text-center">
            <Power className="h-8 w-8 text-muted-foreground" />
            <h2 className="mt-4 text-base font-semibold">Nenhuma maquina cadastrada</h2>
            <p className="mt-2 max-w-md text-sm text-muted-foreground">
              Adicione a primeira maquina para iniciar o inventario do modulo Impressoras.
            </p>
            {canCreate && (
              <Button type="button" onClick={openCreateDialog} className="mt-4">
                <Plus className="h-4 w-4" />
                Adicionar maquina
              </Button>
            )}
          </div>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <SortableHead
                  label="Nome"
                  sortKey="name"
                  activeKey={sortKey}
                  direction={sortDirection}
                  onSort={handleSort}
                />
                <SortableHead
                  label="IP"
                  sortKey="ip_address"
                  activeKey={sortKey}
                  direction={sortDirection}
                  onSort={handleSort}
                />
                <SortableHead
                  label="Fabricante"
                  sortKey="manufacturer"
                  activeKey={sortKey}
                  direction={sortDirection}
                  onSort={handleSort}
                />
                <SortableHead
                  label="Modelo"
                  sortKey="model"
                  activeKey={sortKey}
                  direction={sortDirection}
                  onSort={handleSort}
                />
                <SortableHead
                  label="Setor"
                  sortKey="sector"
                  activeKey={sortKey}
                  direction={sortDirection}
                  onSort={handleSort}
                />
                <SortableHead
                  label="Status"
                  sortKey="is_active"
                  activeKey={sortKey}
                  direction={sortDirection}
                  onSort={handleSort}
                />
                <TableHead className="w-[150px] text-right">Acoes</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {sortedMachines.map((machine) => (
                <TableRow key={machine.id} className="hover:bg-primary/10 dark:hover:bg-primary/20">
                  <TableCell className="font-medium">{machine.name}</TableCell>
                  <TableCell>{machine.ip_address}</TableCell>
                  <TableCell>{machine.manufacturer ?? "-"}</TableCell>
                  <TableCell>{machine.model ?? "-"}</TableCell>
                  <TableCell>{machine.sector ?? "-"}</TableCell>
                  <TableCell>
                    <Badge variant={machine.is_active ? "default" : "outline"}>
                      {machine.is_active ? "Ativa" : "Inativa"}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    <div className="flex justify-end gap-1">
                      {canEdit && (
                        <Button
                          type="button"
                          variant="ghost"
                          size="icon"
                          onClick={() => openEditDialog(machine)}
                          aria-label={`Editar ${machine.name}`}
                        >
                          <Edit className="h-4 w-4" />
                        </Button>
                      )}
                      {canToggle && (
                        <Button
                          type="button"
                          variant="ghost"
                          size="icon"
                          onClick={() => void toggleStatus(machine)}
                          aria-label={machine.is_active ? `Inativar ${machine.name}` : `Ativar ${machine.name}`}
                        >
                          {machine.is_active ? <PowerOff className="h-4 w-4" /> : <Power className="h-4 w-4" />}
                        </Button>
                      )}
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </section>

      <MachineFormDialog
        open={dialogOpen}
        machine={selectedMachine}
        saving={saving}
        error={formError}
        onOpenChange={setDialogOpen}
        onSubmit={handleSubmit}
      />
    </div>
  );
}

function getSortValue(machine: PrinterMachine, key: SortKey) {
  if (key === "is_active") return machine.is_active ? "Ativa" : "Inativa";
  return String(machine[key] ?? "");
}

function SortableHead({
  label,
  sortKey,
  activeKey,
  direction,
  onSort,
}: {
  label: string;
  sortKey: SortKey;
  activeKey: SortKey;
  direction: SortDirection;
  onSort: (key: SortKey) => void;
}) {
  const isActive = activeKey === sortKey;
  const Icon = isActive ? (direction === "asc" ? ArrowDownAZ : ArrowUpAZ) : ChevronsUpDown;

  return (
    <TableHead aria-sort={isActive ? (direction === "asc" ? "ascending" : "descending") : "none"}>
      <button
        type="button"
        onClick={() => onSort(sortKey)}
        className="inline-flex h-8 items-center gap-1.5 rounded-sm px-1 text-left font-medium text-muted-foreground transition-colors hover:bg-primary/10 hover:text-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring dark:hover:bg-primary/20"
      >
        {label}
        <Icon className="h-3.5 w-3.5" />
      </button>
    </TableHead>
  );
}
