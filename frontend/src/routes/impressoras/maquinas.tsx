import { createFileRoute } from "@tanstack/react-router";

import { MachinesPage } from "@/modules/printers/machines/MachinesPage";

export const Route = createFileRoute("/impressoras/maquinas")({
  component: MachinesPage,
  head: () => ({ meta: [{ title: "Máquinas - Sistema ERP" }] }),
});
