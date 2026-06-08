import { LayoutDashboard } from "lucide-react";

export function DashboardPlaceholder() {
  return (
    <section className="mx-auto max-w-[1100px] rounded-lg border border-border/70 bg-card px-6 py-10 shadow-[var(--shadow-card)]">
      <LayoutDashboard className="h-7 w-7 text-primary" />
      <p className="mt-5 text-xs font-medium uppercase tracking-wide text-primary">Impressoras</p>
      <h1 className="mt-2 text-2xl font-semibold">Dashboard</h1>
      <p className="mt-3 max-w-xl text-sm leading-6 text-muted-foreground">
        Módulo em desenvolvimento. Funcionalidade será implementada nas próximas etapas.
      </p>
    </section>
  );
}
