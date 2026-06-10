import { useEffect, useState, type FormEvent, type ReactNode } from "react";
import { Loader2, Save, X } from "lucide-react";

import type {
  PrinterMachine,
  PrinterMachinePayload,
} from "@/modules/printers/machines/machinesApi";
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
import { Switch } from "@/shared/ui/switch";
import { cn } from "@/shared/lib/utils";

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
  fieldErrors,
  onOpenChange,
  onSubmit,
}: {
  open: boolean;
  machine: PrinterMachine | null;
  saving: boolean;
  error: string | null;
  fieldErrors: Record<string, string[]>;
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
      <DialogContent className="h-[min(92dvh,780px)] max-w-[1180px] overflow-hidden p-0">
        <form onSubmit={handleSubmit} className="flex h-full min-h-0 flex-col">
          <div className="flex flex-col gap-3 border-b border-border px-4 py-3.5 pr-14 sm:flex-row sm:items-start sm:justify-between sm:px-5 sm:py-4">
            <DialogHeader>
              <DialogTitle>{machine ? "Editar máquina" : "Adicionar máquina"}</DialogTitle>
              <DialogDescription>Cadastro operacional do módulo Impressoras.</DialogDescription>
            </DialogHeader>

            <div
              className={cn(
                "flex shrink-0 items-center gap-3 rounded-md border px-3 py-2",
                form.is_active
                  ? "border-emerald-500/40 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300"
                  : "border-red-500/40 bg-red-500/10 text-red-700 dark:text-red-300",
              )}
            >
              <div className="text-right">
                <p className="text-xs font-semibold uppercase">
                  {form.is_active ? "Ativa" : "Inativa"}
                </p>
                <p className="text-[11px] text-muted-foreground">Status cadastral</p>
              </div>
              <Switch
                checked={Boolean(form.is_active)}
                onCheckedChange={(checked) =>
                  setForm((current) => ({ ...current, is_active: checked }))
                }
                className="data-[state=checked]:bg-emerald-600 data-[state=unchecked]:bg-red-600"
              />
            </div>
          </div>

          <ScrollArea className="min-h-0 flex-1">
            <div className="space-y-4 px-4 py-3.5 sm:px-5 sm:py-4">
              {error && (
                <p className="rounded-md border border-destructive/30 bg-destructive/8 px-3 py-2 text-sm font-medium text-destructive">
                  {error}
                </p>
              )}

              <div className="grid gap-4 md:grid-cols-2">
                <FormField
                  label="Nome da máquina"
                  htmlFor="machine-name"
                  error={fieldErrors.nome?.[0]}
                >
                  <Input
                    id="machine-name"
                    value={form.name}
                    onChange={(event) =>
                      setForm((current) => ({ ...current, name: event.target.value }))
                    }
                    maxLength={160}
                    required
                  />
                </FormField>

                <FormField label="IP" htmlFor="machine-ip" error={fieldErrors.endereco_ip?.[0]}>
                  <Input
                    id="machine-ip"
                    value={form.ip_address}
                    onChange={(event) =>
                      setForm((current) => ({ ...current, ip_address: event.target.value }))
                    }
                    maxLength={45}
                    required
                  />
                </FormField>

                <FormField
                  label="Fabricante"
                  htmlFor="machine-manufacturer"
                  error={fieldErrors.fabricante?.[0]}
                >
                  <Input
                    id="machine-manufacturer"
                    value={form.manufacturer ?? ""}
                    onChange={(event) =>
                      setForm((current) => ({ ...current, manufacturer: event.target.value }))
                    }
                    maxLength={120}
                  />
                </FormField>

                <FormField label="Modelo" htmlFor="machine-model" error={fieldErrors.modelo?.[0]}>
                  <Input
                    id="machine-model"
                    value={form.model ?? ""}
                    onChange={(event) =>
                      setForm((current) => ({ ...current, model: event.target.value }))
                    }
                    maxLength={120}
                  />
                </FormField>

                <FormField label="Setor" htmlFor="machine-sector" error={fieldErrors.setor?.[0]}>
                  <Input
                    id="machine-sector"
                    value={form.sector ?? ""}
                    onChange={(event) =>
                      setForm((current) => ({ ...current, sector: event.target.value }))
                    }
                    maxLength={120}
                  />
                </FormField>

                <FormField
                  label="Centro de custo"
                  htmlFor="machine-cost-center"
                  error={fieldErrors.centro_custo?.[0]}
                >
                  <Input
                    id="machine-cost-center"
                    value={form.cost_center ?? ""}
                    onChange={(event) =>
                      setForm((current) => ({ ...current, cost_center: event.target.value }))
                    }
                    maxLength={80}
                  />
                </FormField>
              </div>

              <FormField
                label="Observações"
                htmlFor="machine-notes"
                error={fieldErrors.observacoes?.[0]}
              >
                <textarea
                  id="machine-notes"
                  value={form.notes ?? ""}
                  onChange={(event) =>
                    setForm((current) => ({ ...current, notes: event.target.value }))
                  }
                  className="min-h-24 w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm shadow-sm transition-colors placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
                />
              </FormField>
            </div>
          </ScrollArea>

          <DialogFooter className="shrink-0 border-t border-border bg-card/95 px-4 py-3 sm:px-5 sm:py-3.5">
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
              disabled={saving}
            >
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

function FormField({
  label,
  htmlFor,
  error,
  children,
}: {
  label: string;
  htmlFor: string;
  error?: string;
  children: ReactNode;
}) {
  return (
    <div className="space-y-1.5">
      <div className="flex min-h-5 items-center justify-between gap-2">
        <Label htmlFor={htmlFor}>{label}</Label>
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
