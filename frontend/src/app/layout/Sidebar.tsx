import { Link, useNavigate, useRouterState } from "@tanstack/react-router";
import { ExternalLink, Files, Home, LayoutDashboard, LogOut, Printer, UserRound } from "lucide-react";

import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarMenuSub,
  SidebarMenuSubButton,
  SidebarMenuSubItem,
  useSidebar,
} from "@/shared/ui/sidebar";
import { useAuth } from "@/modules/auth/authStore";
import type { PortalPermissionKey } from "@/modules/auth/authApi";
import { cn } from "@/shared/lib/utils";

const items = [
  { title: "Inicio", url: "/inicio", icon: Home, permission: "can_access_portal" },
] as const;

const printerModuleItem = {
  title: "Impressoras",
  url: "/impressoras/dashboard",
  icon: LayoutDashboard,
  permission: "can_access_printers_dashboard",
} as const;

const printerItems = [
  {
    title: "Máquinas",
    url: "/impressoras/maquinas",
    icon: Printer,
    permission: "can_access_printers_machines",
  },
  {
    title: "Papel",
    url: "/impressoras/papel",
    icon: Files,
    permission: "can_access_printers_paper",
  },
] as const;

const ADMIN_URL = import.meta.env.VITE_ADMIN_URL ?? "/admin/";

const sidebarLogoSrc = "/static/imgs/industria-logo-white.png";

function getUserInitials(name?: string | null, username?: string | null) {
  const value = (name || username || "industria").trim();
  const parts = value.split(/\s+/).filter(Boolean);

  if (parts.length >= 2) {
    return `${parts[0][0]}${parts[parts.length - 1][0]}`.toUpperCase();
  }

  return value.slice(0, 2).toUpperCase();
}

export function AppSidebar() {
  const navigate = useNavigate();
  const { user, hasPermission, logout } = useAuth();
  const { state } = useSidebar();
  const collapsed = state === "collapsed";
  const pathname = useRouterState({ select: (r) => r.location.pathname });
  const visibleItems = items.filter((item) => hasPermission(item.permission as PortalPermissionKey));
  const visiblePrinterItems = printerItems.filter((item) => hasPermission(item.permission as PortalPermissionKey));
  const canAccessPrintersModule =
    hasPermission("can_access_printers") && hasPermission(printerModuleItem.permission);
  const homeUrl = (visibleItems[0]?.url ?? "/inicio") as "/inicio";
  const profileImageUrl = (user as { profile_image_url?: string | null } | null)?.profile_image_url;

  async function handleLogout() {
    await logout();
    await navigate({ to: "/login", replace: true });
  }

  return (
    <Sidebar collapsible="icon" className="border-r border-sidebar-border bg-sidebar">
      <SidebarHeader className="h-20 border-b border-sidebar-border/80 bg-[linear-gradient(180deg,color-mix(in_oklab,var(--industria-blue-bright)_14%,transparent),transparent)]">
        <Link to={homeUrl} className="flex h-full items-center gap-3 px-2 py-2">
          <div
            className={cn(
              "flex shrink-0 items-center justify-center overflow-hidden border border-white/15 bg-white/[0.08] shadow-[var(--shadow-elegant)]",
              collapsed ? "h-11 w-11 rounded-xl" : "h-16 w-16 rounded-2xl",
            )}
          >
            {profileImageUrl ? (
              <img
                src={profileImageUrl}
                alt={user?.display_name ? `Foto de ${user.display_name}` : "Foto do usuario"}
                className="h-full w-full object-cover"
              />
            ) : (
              <div className="flex h-full w-full flex-col items-center justify-center bg-[radial-gradient(circle_at_30%_20%,color-mix(in_oklab,var(--industria-blue-bright)_40%,transparent),transparent_55%),linear-gradient(135deg,color-mix(in_oklab,var(--industria-blue)_70%,#ffffff),var(--industria-blue-dark))]">
                <UserRound className={cn("text-white/90", collapsed ? "h-5 w-5" : "h-7 w-7")} />
                {!collapsed && (
                  <span className="mt-0.5 text-[10px] font-semibold leading-none tracking-wide text-white">
                    {getUserInitials(user?.display_name, user?.username)}
                  </span>
                )}
              </div>
            )}
          </div>
          {!collapsed && (
            <div className="flex min-w-0 flex-col gap-1">
              <img src={sidebarLogoSrc} alt="Grupo industria" className="h-7 w-auto object-contain object-left" />
              <span className="truncate text-[11px] text-sidebar-foreground/70">Portal industria</span>
            </div>
          )}
        </Link>
      </SidebarHeader>

      <SidebarContent>
        <SidebarGroup>
          {!collapsed && <SidebarGroupLabel className="text-sidebar-foreground/60">Navegacao</SidebarGroupLabel>}
          <SidebarGroupContent>
            <SidebarMenu>
              {visibleItems.map((item) => {
                const active = pathname.startsWith(item.url);
                return (
                  <SidebarMenuItem key={item.url}>
                    <SidebarMenuButton asChild isActive={active} tooltip={item.title}>
                      <Link
                        to={item.url}
                        className={cn(
                          "group/link flex items-center gap-2.5 rounded-md text-sidebar-foreground/80 transition-colors hover:bg-sidebar-accent/70 hover:text-sidebar-accent-foreground",
                          active &&
                            "bg-sidebar-accent text-sidebar-accent-foreground font-medium shadow-[inset_3px_0_0_var(--sidebar-primary)]",
                        )}
                      >
                        <item.icon className={cn("h-4 w-4 shrink-0", active && "text-sidebar-primary")} />
                        <span>{item.title}</span>
                        {active && <span className="ml-auto h-1.5 w-1.5 rounded-full bg-sidebar-primary" />}
                      </Link>
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                );
              })}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>

        {canAccessPrintersModule && (
          <SidebarGroup>
            {!collapsed && <SidebarGroupLabel className="text-sidebar-foreground/60">Módulos</SidebarGroupLabel>}
            <SidebarGroupContent>
              <SidebarMenu>
                <SidebarMenuItem>
                  <SidebarMenuButton asChild isActive={pathname.startsWith("/impressoras")} tooltip={printerModuleItem.title}>
                    <Link
                      to={printerModuleItem.url}
                      className={cn(
                        "group/link flex items-center gap-2.5 rounded-md text-sidebar-foreground/80 transition-colors hover:bg-sidebar-accent/70 hover:text-sidebar-accent-foreground",
                        pathname.startsWith("/impressoras") &&
                          "bg-sidebar-accent text-sidebar-accent-foreground font-medium shadow-[inset_3px_0_0_var(--sidebar-primary)]",
                      )}
                    >
                      <printerModuleItem.icon
                        className={cn("h-4 w-4 shrink-0", pathname.startsWith("/impressoras") && "text-sidebar-primary")}
                      />
                      <span>{printerModuleItem.title}</span>
                      {pathname.startsWith("/impressoras") && <span className="ml-auto h-1.5 w-1.5 rounded-full bg-sidebar-primary" />}
                    </Link>
                  </SidebarMenuButton>
                  {visiblePrinterItems.length > 0 && (
                    <SidebarMenuSub>
                      {visiblePrinterItems.map((item) => {
                        const active = pathname.startsWith(item.url);
                        return (
                          <SidebarMenuSubItem key={item.url}>
                            <SidebarMenuSubButton asChild isActive={active}>
                              <Link to={item.url}>
                                <item.icon className={cn("h-4 w-4 shrink-0", active && "text-sidebar-primary")} />
                                <span>{item.title}</span>
                              </Link>
                            </SidebarMenuSubButton>
                          </SidebarMenuSubItem>
                        );
                      })}
                    </SidebarMenuSub>
                  )}
                </SidebarMenuItem>
              </SidebarMenu>
            </SidebarGroupContent>
          </SidebarGroup>
        )}

        {user?.permissions.can_access_admin && (
          <SidebarGroup>
            {!collapsed && <SidebarGroupLabel className="text-sidebar-foreground/60">Sistema</SidebarGroupLabel>}
            <SidebarGroupContent>
              <SidebarMenu>
                <SidebarMenuItem>
                  <SidebarMenuButton asChild tooltip="Admin (Django)">
                    <a
                      href={ADMIN_URL}
                      target="_blank"
                      rel="noreferrer"
                      className="flex items-center gap-2.5 text-sidebar-foreground/80 hover:bg-sidebar-accent/70 hover:text-sidebar-accent-foreground"
                    >
                      <ExternalLink className="h-4 w-4 shrink-0" />
                      <span>Admin</span>
                      <span className="ml-auto rounded bg-white/10 px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide text-sidebar-foreground/70">
                        Django
                      </span>
                    </a>
                  </SidebarMenuButton>
                </SidebarMenuItem>
              </SidebarMenu>
            </SidebarGroupContent>
          </SidebarGroup>
        )}
      </SidebarContent>

      <SidebarFooter className="border-t border-sidebar-border/70">
        {!collapsed && (
          <div className="space-y-2 rounded-lg border border-sidebar-border/60 bg-white/[0.04] px-2 py-2 text-[11px] text-sidebar-foreground/70">
            <div>
              <p className="font-medium text-white">{user?.display_name ?? "industria"}</p>
              <p>v2 base</p>
            </div>
            <button
              type="button"
              onClick={handleLogout}
              className="flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-sidebar-foreground/80 transition-colors hover:bg-sidebar-accent/70 hover:text-sidebar-accent-foreground"
            >
              <LogOut className="h-3.5 w-3.5" />
              Sair
            </button>
          </div>
        )}
        {collapsed && (
          <button
            type="button"
            onClick={handleLogout}
            className="mx-auto flex h-8 w-8 items-center justify-center rounded-md text-sidebar-foreground/80 hover:bg-sidebar-accent/70"
            aria-label="Sair"
          >
            <LogOut className="h-4 w-4" />
          </button>
        )}
      </SidebarFooter>
    </Sidebar>
  );
}
