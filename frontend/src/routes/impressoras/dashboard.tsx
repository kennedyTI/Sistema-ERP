import { createFileRoute } from "@tanstack/react-router";

import { DashboardPage } from "@/modules/printers/dashboard/DashboardPage";

export const Route = createFileRoute("/impressoras/dashboard")({
  component: DashboardPage,
  head: () => ({ meta: [{ title: "Dashboard de Impressoras - Sistema ERP" }] }),
});
