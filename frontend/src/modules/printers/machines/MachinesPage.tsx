import { RequireAuth } from "@/modules/auth/RequireAuth";
import { MachinesPlaceholder } from "@/modules/printers/machines/components/MachinesPlaceholder";

export function MachinesPage() {
  return (
    <RequireAuth permission="can_access_printers_machines">
      <MachinesPlaceholder />
    </RequireAuth>
  );
}
