import { createFileRoute } from "@tanstack/react-router";

import { PaperPage } from "@/modules/printers/paper/PaperPage";

export const Route = createFileRoute("/impressoras/papel")({
  component: PaperPage,
  head: () => ({ meta: [{ title: "Papel - Sistema ERP" }] }),
});
