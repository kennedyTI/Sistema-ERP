import type { LucideIcon } from "lucide-react";

import { Skeleton } from "@/shared/ui/skeleton";
import { cn } from "@/shared/lib/utils";

export interface PrinterSummaryCard {
  key: string;
  label: string;
  subtitle: string;
  value: number;
  icon: LucideIcon;
  accent: string;
  iconStyle: string;
}

export function PrinterSummaryCards({
  cards,
  loading,
  label,
}: {
  cards: PrinterSummaryCard[];
  loading: boolean;
  label: string;
}) {
  return (
    <section
      className="grid auto-rows-fr grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5"
      aria-label={label}
    >
      {cards.map((card) => (
        <article
          key={card.key}
          className={cn(
            "relative flex min-h-[112px] flex-col overflow-hidden rounded-lg border border-border/70 border-t-[3px] bg-card/80 px-4 py-3.5 text-card-foreground shadow-[var(--shadow-card)] backdrop-blur-sm",
            card.accent,
          )}
        >
          <div
            className={cn(
              "absolute right-3.5 top-3.5 flex h-9 w-9 items-center justify-center rounded-full",
              card.iconStyle,
            )}
          >
            <card.icon className="h-4 w-4" aria-hidden="true" />
          </div>
          <p className="flex min-h-8 max-w-[72%] items-start text-xs font-medium leading-4 text-muted-foreground">
            {card.label}
          </p>
          {loading ? (
            <Skeleton className="mt-1 h-7 w-16" />
          ) : (
            <p className="mt-1 text-2xl font-semibold tabular-nums">{card.value}</p>
          )}
          <p className="mt-auto pt-0.5 text-[11px] leading-4 text-muted-foreground">
            {card.subtitle}
          </p>
        </article>
      ))}
    </section>
  );
}
