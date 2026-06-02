import type { PortalPermissions } from "@/modules/auth/authApi";

export type PortalRoute = "/inicio";

export function getDefaultPortalRoute(permissions: PortalPermissions): PortalRoute | null {
  if (permissions.can_access_portal) return "/inicio";
  return null;
}

