import { useEffect, useMemo, useState } from "react";
import { Edit, Loader2, Plus, Power, PowerOff, RefreshCw } from "lucide-react";

import { RequireAuth } from "@/modules/auth/RequireAuth";
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

export function MachinesPage() {
  return (
    <RequireAuth permission="can_access_printers_machines">
      <MachinesContent />
    </RequireAuth>
  );
}

function MachinesContent() {
  const [machines, setMachines] = useState<PrinterMachine[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [selectedMachine, setSelectedMachine] = useState<PrinterMachine | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);

  const activeCount = useMemo(() => machines.filter((machine) => machine.is_active).length, [machines]);

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
        await updatePrinterMachine(selectedMachine.id, payload);
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
            <Button type="button" onClick={openCreateDialog}>
              <Plus className="h-4 w-4" />
              Adicionar maquina
            </Button>
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
            <Button type="button" onClick={openCreateDialog} className="mt-4">
              <Plus className="h-4 w-4" />
              Adicionar maquina
            </Button>
          </div>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Nome</TableHead>
                <TableHead>IP</TableHead>
                <TableHead>Fabricante</TableHead>
                <TableHead>Modelo</TableHead>
                <TableHead>Setor</TableHead>
                <TableHead>Status</TableHead>
                <TableHead className="w-[150px] text-right">Acoes</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {machines.map((machine) => (
                <TableRow key={machine.id}>
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
                      <Button
                        type="button"
                        variant="ghost"
                        size="icon"
                        onClick={() => openEditDialog(machine)}
                        aria-label={`Editar ${machine.name}`}
                      >
                        <Edit className="h-4 w-4" />
                      </Button>
                      <Button
                        type="button"
                        variant="ghost"
                        size="icon"
                        onClick={() => void toggleStatus(machine)}
                        aria-label={machine.is_active ? `Inativar ${machine.name}` : `Ativar ${machine.name}`}
                      >
                        {machine.is_active ? <PowerOff className="h-4 w-4" /> : <Power className="h-4 w-4" />}
                      </Button>
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
