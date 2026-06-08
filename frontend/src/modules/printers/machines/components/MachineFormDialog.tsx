import { useEffect, useState, type FormEvent } from "react";
import { Loader2, Save } from "lucide-react";

import type { PrinterMachine, PrinterMachinePayload } from "@/modules/printers/machines/machinesApi";
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
import { Switch } from "@/shared/ui/switch";

type MachineFormState = Required<Pick<PrinterMachinePayload, "name" | "ip_address">> &
  Omit<PrinterMachinePayload, "name" | "ip_address">;

const emptyForm: MachineFormState = {
  name: "",
  ip_address: "",
  manufacturer: "",
  model: "",
  sector: "",
  cost_center: "",
  is_active: true,
  notes: "",
};

function toFormState(machine: PrinterMachine | null): MachineFormState {
  if (!machine) return emptyForm;

  return {
    name: machine.name,
    ip_address: machine.ip_address,
    manufacturer: machine.manufacturer ?? "",
    model: machine.model ?? "",
    sector: machine.sector ?? "",
    cost_center: machine.cost_center ?? "",
    is_active: machine.is_active,
    notes: machine.notes ?? "",
  };
}

function cleanOptional(value: string | null | undefined) {
  const trimmed = value?.trim() ?? "";
  return trimmed || null;
}

export function MachineFormDialog({
  open,
  machine,
  saving,
  error,
  onOpenChange,
  onSubmit,
}: {
  open: boolean;
  machine: PrinterMachine | null;
  saving: boolean;
  error: string | null;
  onOpenChange: (open: boolean) => void;
  onSubmit: (payload: PrinterMachinePayload) => Promise<void>;
}) {
  const [form, setForm] = useState<MachineFormState>(emptyForm);

  useEffect(() => {
    if (open) setForm(toFormState(machine));
  }, [machine, open]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await onSubmit({
      name: form.name.trim(),
      ip_address: form.ip_address.trim(),
      manufacturer: cleanOptional(form.manufacturer),
      model: cleanOptional(form.model),
      sector: cleanOptional(form.sector),
      cost_center: cleanOptional(form.cost_center),
      is_active: form.is_active,
      notes: cleanOptional(form.notes),
    });
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <DialogHeader>
            <DialogTitle>{machine ? "Editar maquina" : "Adicionar maquina"}</DialogTitle>
            <DialogDescription>Cadastro operacional inicial do modulo Impressoras.</DialogDescription>
          </DialogHeader>

          <div
            className={
              "flex shrink-0 items-center gap-3 rounded-md border px-3 py-2 " +
              (form.is_active
                ? "border-emerald-500/40 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300"
                : "border-red-500/40 bg-red-500/10 text-red-700 dark:text-red-300")
            }
          >
            <div className="text-right">
              <p className="text-xs font-semibold uppercase tracking-wide">
                {form.is_active ? "Ativa" : "Inativa"}
              </p>
              <p className="text-[11px] text-muted-foreground">Status</p>
            </div>
            <Switch
              checked={Boolean(form.is_active)}
              onCheckedChange={(checked) => setForm((current) => ({ ...current, is_active: checked }))}
              className="data-[state=checked]:bg-emerald-600 data-[state=unchecked]:bg-red-600"
            />
          </div>
        </div>

        <form onSubmit={handleSubmit} className="space-y-5">
          <div className="grid gap-4 md:grid-cols-2">
            <div className="space-y-1.5">
              <Label htmlFor="machine-name">Nome</Label>
              <Input
                id="machine-name"
                value={form.name}
                onChange={(event) => setForm((current) => ({ ...current, name: event.target.value }))}
                maxLength={160}
                required
              />
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="machine-ip">IP</Label>
              <Input
                id="machine-ip"
                value={form.ip_address}
                onChange={(event) => setForm((current) => ({ ...current, ip_address: event.target.value }))}
                maxLength={45}
                required
              />
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="machine-manufacturer">Fabricante</Label>
              <Input
                id="machine-manufacturer"
                value={form.manufacturer ?? ""}
                onChange={(event) => setForm((current) => ({ ...current, manufacturer: event.target.value }))}
                maxLength={120}
              />
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="machine-model">Modelo</Label>
              <Input
                id="machine-model"
                value={form.model ?? ""}
                onChange={(event) => setForm((current) => ({ ...current, model: event.target.value }))}
                maxLength={120}
              />
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="machine-sector">Setor</Label>
              <Input
                id="machine-sector"
                value={form.sector ?? ""}
                onChange={(event) => setForm((current) => ({ ...current, sector: event.target.value }))}
                maxLength={120}
              />
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="machine-cost-center">Centro de custo</Label>
              <Input
                id="machine-cost-center"
                value={form.cost_center ?? ""}
                onChange={(event) => setForm((current) => ({ ...current, cost_center: event.target.value }))}
                maxLength={80}
              />
            </div>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="machine-notes">Observacoes</Label>
            <textarea
              id="machine-notes"
              value={form.notes ?? ""}
              onChange={(event) => setForm((current) => ({ ...current, notes: event.target.value }))}
              className="min-h-24 w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm shadow-sm transition-colors placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
            />
          </div>

          <div className="min-h-5">
            {error && <p className="text-sm font-medium text-destructive">{error}</p>}
          </div>

          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)} disabled={saving}>
              Cancelar
            </Button>
            <Button type="submit" disabled={saving}>
              {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
              Salvar
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
