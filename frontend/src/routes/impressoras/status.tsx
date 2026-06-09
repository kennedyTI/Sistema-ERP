import { createFileRoute } from "@tanstack/react-router";

import { StatusPage } from "@/modules/printers/status/StatusPage";

export const Route = createFileRoute("/impressoras/status")({
  component: StatusPage,
  head: () => ({ meta: [{ title: "Status - Sistema ERP" }] }),
});
