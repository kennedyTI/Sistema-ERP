import { createFileRoute } from "@tanstack/react-router";

import { HomePage } from "@/modules/home/HomePage";

export const Route = createFileRoute("/inicio")({
  component: HomePage,
  head: () => ({ meta: [{ title: "Inicio - Portal industria" }] }),
});
