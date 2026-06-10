import {
  Building2,
  CircleOff,
  Layers3,
  Printer,
  PrinterCheck,
  type LucideIcon,
} from "lucide-react";

import type { PrinterMachineSummary } from "@/modules/printers/machines/machinesApi";
import { Skeleton } from "@/shared/ui/skeleton";
import { cn } from "@/shared/lib/utils";

const cards: Array<{
  key: keyof PrinterMachineSummary;
  label: string;
  subtitle: string;
  icon: LucideIcon;
  accent: string;
  iconStyle: string;
}> = [
  {
    key: "total_machines",
    label: "Total de máquinas",
    subtitle: "Inventário cadastrado",
    icon: Printer,
    accent: "border-t-sky-400",
    iconStyle: "bg-sky-400/15 text-sky-300",
  },
  {
    key: "active",
    label: "Ativas",
    subtitle: "Disponíveis no cadastro",
    icon: PrinterCheck,
    accent: "border-t-emerald-400",
    iconStyle: "bg-emerald-400/15 text-emerald-300",
  },
  {
    key: "inactive",
    label: "Inativas",
    subtitle: "Mantidas no histórico",
    icon: CircleOff,
    accent: "border-t-rose-400",
    iconStyle: "bg-rose-400/15 text-rose-300",
  },
  {
    key: "manufacturers",
    label: "Fabricantes",
    subtitle: "Marcas vinculadas",
    icon: Building2,
    accent: "border-t-amber-400",
    iconStyle: "bg-amber-400/15 text-amber-300",
  },
  {
    key: "registered_models",
    label: "Modelos cadastrados",
    subtitle: "Catálogo de equipamentos",
    icon: Layers3,
    accent: "border-t-cyan-400",
    iconStyle: "bg-cyan-400/15 text-cyan-300",
  },
];

export function MachinesSummaryCards({
  summary,
  loading,
}: {
  summary: PrinterMachineSummary | null;
  loading: boolean;
}) {
  return (
    <section
      className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-5"
      aria-label="Resumo cadastral de máquinas"
    >
      {cards.map((card) => (
        <article
          key={card.key}
          className={cn(
            "relative min-h-32 overflow-hidden rounded-lg border border-zinc-700 border-t-4 bg-zinc-900 px-5 py-4 text-zinc-50 shadow-[var(--shadow-card)]",
            card.accent,
          )}
        >
          <div
            className={cn(
              "absolute right-4 top-4 flex h-11 w-11 items-center justify-center rounded-full",
              card.iconStyle,
            )}
          >
            <card.icon className="h-5 w-5" aria-hidden="true" />
          </div>
          <p className="max-w-[70%] text-sm font-medium text-zinc-300">{card.label}</p>
          {loading ? (
            <Skeleton className="mt-4 h-9 w-20 bg-white/10" />
          ) : (
            <p className="mt-3 text-3xl font-semibold tabular-nums">{summary?.[card.key] ?? 0}</p>
          )}
          <p className="mt-1 text-xs text-zinc-400">{card.subtitle}</p>
        </article>
      ))}
    </section>
  );
}
