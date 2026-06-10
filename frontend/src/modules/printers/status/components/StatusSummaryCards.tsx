import { CircleAlert, Droplet, Printer, Wifi, WifiOff } from "lucide-react";

import { PrinterSummaryCards } from "@/modules/printers/shared/PrinterSummaryCards";
import type { PrinterStatusSummary } from "@/modules/printers/status/statusApi";

export function StatusSummaryCards({
  summary,
  loading,
}: {
  summary: PrinterStatusSummary | null;
  loading: boolean;
}) {
  const cards = [
    {
      key: "total_impressoras",
      label: "Total de impressoras",
      subtitle: "Equipamentos monitorados",
      value: summary?.total_impressoras ?? 0,
      icon: Printer,
      accent: "border-t-sky-500",
      iconStyle: "bg-sky-500/12 text-sky-600 dark:text-sky-300",
    },
    {
      key: "online",
      label: "Online",
      subtitle: "Respondendo normalmente",
      value: summary?.online ?? 0,
      icon: Wifi,
      accent: "border-t-emerald-500",
      iconStyle: "bg-emerald-500/12 text-emerald-600 dark:text-emerald-300",
    },
    {
      key: "offline",
      label: "Offline",
      subtitle: "Sem comunicação",
      value: summary?.offline ?? 0,
      icon: WifiOff,
      accent: "border-t-rose-500",
      iconStyle: "bg-rose-500/12 text-rose-600 dark:text-rose-300",
    },
    {
      key: "com_alerta",
      label: "Com alerta",
      subtitle: "Exigem atenção",
      value: summary?.com_alerta ?? 0,
      icon: CircleAlert,
      accent: "border-t-amber-500",
      iconStyle: "bg-amber-500/12 text-amber-600 dark:text-amber-300",
    },
    {
      key: "substituir_toner",
      label: "Substituir toner",
      subtitle: "Ação de suprimento",
      value: summary?.substituir_toner ?? 0,
      icon: Droplet,
      accent: "border-t-orange-500",
      iconStyle: "bg-orange-500/12 text-orange-600 dark:text-orange-300",
    },
  ];

  return <PrinterSummaryCards cards={cards} loading={loading} label="Resumo operacional" />;
}
