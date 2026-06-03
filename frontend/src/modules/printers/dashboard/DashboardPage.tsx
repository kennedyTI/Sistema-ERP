import { RequireAuth } from "@/modules/auth/RequireAuth";
import { DashboardPlaceholder } from "@/modules/printers/dashboard/components/DashboardPlaceholder";

export function DashboardPage() {
  return (
    <RequireAuth permission="can_access_printers_dashboard">
      <DashboardPlaceholder />
    </RequireAuth>
  );
}
