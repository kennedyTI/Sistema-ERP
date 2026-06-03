import { ExternalLink, UserRound } from "lucide-react";

import { RequireAuth } from "@/modules/auth/RequireAuth";
import { Button } from "@/shared/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/ui/card";
import { useAuth } from "@/modules/auth/authStore";

const ADMIN_URL = import.meta.env.VITE_ADMIN_URL ?? "/admin/";

export function HomePage() {
  return (
    <RequireAuth permission="can_access_portal">
      <InicioPage />
    </RequireAuth>
  );
}

function InicioPage() {
  const { user } = useAuth();
  const groups = user?.groups.length ? user.groups.join(", ") : "Sem grupo vinculado";

  return (
    <div className="mx-auto flex max-w-[1100px] flex-col gap-6">
      <section className="rounded-lg border border-border/70 bg-card px-6 py-6 shadow-[var(--shadow-card)]">
        <div className="flex flex-col gap-5 md:flex-row md:items-center md:justify-between">
          <div>
            <p className="text-xs font-medium uppercase tracking-wide text-primary">Portal industria</p>
            <h1 className="mt-2 text-2xl font-semibold tracking-tight">Bem-vindo, {user?.display_name ?? user?.username}</h1>
            <p className="mt-2 max-w-2xl text-sm text-muted-foreground">
              Esta base v2 esta pronta para receber os proximos modulos gradualmente.
            </p>
          </div>
          {user?.permissions.can_access_admin && (
            <Button asChild className="shrink-0">
              <a href={ADMIN_URL} target="_blank" rel="noreferrer">
                <ExternalLink className="h-4 w-4" />
                Admin
              </a>
            </Button>
          )}
        </div>
      </section>

      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <UserRound className="h-4 w-4 text-primary" />
              Seu acesso
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-sm">
            <div>
              <p className="text-xs uppercase tracking-wide text-muted-foreground">Usuario</p>
              <p className="mt-1 font-medium">{user?.username}</p>
            </div>
            <div>
              <p className="text-xs uppercase tracking-wide text-muted-foreground">Perfis</p>
              <p className="mt-1 font-medium">{groups}</p>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Proximos modulos</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm leading-6 text-muted-foreground">
              Os novos modulos serao adicionados depois da reorganizacao modular da v2.
            </p>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}


