import { Building2, CircleOff, Layers3, Printer, PrinterCheck } from "lucide-react";

import type { PrinterMachineSummary } from "@/modules/printers/machines/machinesApi";
import { PrinterSummaryCards } from "@/modules/printers/shared/PrinterSummaryCards";

export function MachinesSummaryCards({
  summary,
  loading,
}: {
  summary: PrinterMachineSummary | null;
  loading: boolean;
}) {
  const cards = [
    {
      key: "total_machines",
      label: "Total de máquinas",
      subtitle: "Inventário cadastrado",
      value: summary?.total_machines ?? 0,
      icon: Printer,
      accent: "border-t-sky-500",
      iconStyle: "bg-sky-500/12 text-sky-600 dark:text-sky-300",
    },
    {
      key: "active",
      label: "Ativas",
      subtitle: "Disponíveis no cadastro",
      value: summary?.active ?? 0,
      icon: PrinterCheck,
      accent: "border-t-emerald-500",
      iconStyle: "bg-emerald-500/12 text-emerald-600 dark:text-emerald-300",
    },
    {
      key: "inactive",
      label: "Inativas",
      subtitle: "Mantidas no histórico",
      value: summary?.inactive ?? 0,
      icon: CircleOff,
      accent: "border-t-rose-500",
      iconStyle: "bg-rose-500/12 text-rose-600 dark:text-rose-300",
    },
    {
      key: "manufacturers",
      label: "Fabricantes",
      subtitle: "Marcas vinculadas",
      value: summary?.manufacturers ?? 0,
      icon: Building2,
      accent: "border-t-amber-500",
      iconStyle: "bg-amber-500/12 text-amber-600 dark:text-amber-300",
    },
    {
      key: "registered_models",
      label: "Modelos cadastrados",
      subtitle: "Catálogo de equipamentos",
      value: summary?.registered_models ?? 0,
      icon: Layers3,
      accent: "border-t-cyan-500",
      iconStyle: "bg-cyan-500/12 text-cyan-600 dark:text-cyan-300",
    },
  ];

  return (
    <PrinterSummaryCards cards={cards} loading={loading} label="Resumo cadastral de máquinas" />
  );
}
