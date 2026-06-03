import { RequireAuth } from "@/modules/auth/RequireAuth";
import { PaperPlaceholder } from "@/modules/printers/paper/components/PaperPlaceholder";

export function PaperPage() {
  return (
    <RequireAuth permission="can_access_printers_paper">
      <PaperPlaceholder />
    </RequireAuth>
  );
}
