import { createFileRoute } from "@tanstack/react-router";

import { LoginPage } from "@/modules/auth/LoginPage";

export const Route = createFileRoute("/login")({
  head: () => ({
    meta: [
      { title: "Acesso - industria" },
      { name: "description", content: "Acesso ao portal interno industria." },
      { name: "robots", content: "noindex,nofollow" },
    ],
  }),
  component: LoginPage,
});
