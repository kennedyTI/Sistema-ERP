import { Outlet, useRouterState } from "@tanstack/react-router";
import { Bell } from "lucide-react";

import { Button } from "@/shared/ui/button";
import { SidebarProvider, SidebarTrigger } from "@/shared/ui/sidebar";
import { AppSidebar } from "./Sidebar";
import { ThemeToggle } from "@/shared/components/ThemeToggle";

const titles: Record<string, { title: string; sub: string }> = {
  "/inicio": { title: "Inicio", sub: "Base v2 do Portal industria" },
  "/impressoras/dashboard": { title: "Dashboard", sub: "Módulo Impressoras" },
  "/impressoras/status": { title: "Status", sub: "Módulo Impressoras" },
  "/impressoras/maquinas": { title: "Máquinas", sub: "Módulo Impressoras" },
  "/impressoras/papel": { title: "Papel", sub: "Módulo Impressoras" },
};

export function AppLayout() {
  const pathname = useRouterState({ select: (r) => r.location.pathname });
  const meta = titles[pathname] ?? { title: "Portal industria", sub: "" };

  return (
    <SidebarProvider>
      <div className="flex min-h-screen w-full bg-background">
        <AppSidebar />
        <div className="flex flex-1 flex-col">
          <header className="sticky top-0 z-30 flex h-16 items-center gap-3 border-b border-border/70 bg-card/86 px-4 shadow-[0_1px_0_color-mix(in_oklab,var(--industria-blue)_8%,transparent)] backdrop-blur supports-[backdrop-filter]:bg-card/74 sm:px-6">
            <SidebarTrigger className="-ml-1 text-primary hover:bg-primary-soft hover:text-primary-dark dark:hover:bg-primary/15 dark:hover:text-primary" />
            <div className="hidden sm:block">
              <h1 className="text-sm font-semibold leading-tight">{meta.title}</h1>
              <p className="text-xs text-muted-foreground">{meta.sub}</p>
            </div>
            <div className="ml-auto flex items-center gap-2">
              <Button variant="ghost" size="icon" className="rounded-full text-primary hover:bg-primary-soft hover:text-primary-dark dark:hover:bg-primary/15 dark:hover:text-primary" aria-label="Notificacoes">
                <Bell className="h-4 w-4" />
              </Button>
              <ThemeToggle />
            </div>
          </header>
          <main className="flex-1 px-4 py-6 sm:px-6 lg:px-8">
            <Outlet />
          </main>
        </div>
      </div>
    </SidebarProvider>
  );
}

