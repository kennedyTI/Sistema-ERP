import { CircleAlert, PackageSearch, Printer, Wifi, WifiOff } from "lucide-react";

import type { PrinterStatusSummary } from "@/modules/printers/status/statusApi";
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/ui/card";
import { Skeleton } from "@/shared/ui/skeleton";
import { cn } from "@/shared/lib/utils";

const cards = [
  {
    key: "total_impressoras",
    label: "Total de impressoras",
    icon: Printer,
    className: "text-primary",
  },
  {
    key: "online",
    label: "Online",
    icon: Wifi,
    className: "text-emerald-600 dark:text-emerald-400",
  },
  {
    key: "offline",
    label: "Offline",
    icon: WifiOff,
    className: "text-red-600 dark:text-red-400",
  },
  {
    key: "com_alerta",
    label: "Com alerta",
    icon: CircleAlert,
    className: "text-amber-600 dark:text-amber-400",
  },
  {
    key: "substituir_toner",
    label: "Substituir toner",
    icon: PackageSearch,
    className: "text-orange-600 dark:text-orange-400",
  },
] as const;

export function StatusSummaryCards({
  summary,
  loading,
}: {
  summary: PrinterStatusSummary | null;
  loading: boolean;
}) {
  return (
    <section className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-5" aria-label="Resumo operacional">
      {cards.map((card) => (
        <Card key={card.key} className="rounded-lg border-border/70 shadow-[var(--shadow-card)]">
          <CardHeader className="flex flex-row items-center justify-between gap-3 space-y-0 pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">{card.label}</CardTitle>
            <card.icon className={cn("h-4 w-4 shrink-0", card.className)} />
          </CardHeader>
          <CardContent>
            {loading ? (
              <Skeleton className="h-8 w-16" />
            ) : (
              <p className="text-2xl font-semibold tabular-nums">{summary?.[card.key] ?? 0}</p>
            )}
          </CardContent>
        </Card>
      ))}
    </section>
  );
}
