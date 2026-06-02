import * as React from "react";
import { useNavigate } from "@tanstack/react-router";
import { LockKeyhole } from "lucide-react";

import { Card } from "@/shared/ui/card";
import { type PortalPermissionKey } from "@/modules/auth/authApi";
import { useAuth } from "@/modules/auth/authStore";

export function RequireAuth({
  permission,
  children,
}: {
  permission: PortalPermissionKey;
  children: React.ReactNode;
}) {
  const navigate = useNavigate();
  const { user, loading, hasPermission } = useAuth();

  React.useEffect(() => {
    if (!loading && !user) {
      void navigate({ to: "/login", replace: true });
    }
  }, [loading, navigate, user]);

  if (loading) {
    return (
      <div className="flex min-h-[50vh] items-center justify-center text-sm text-muted-foreground">
        Carregando sessao...
      </div>
    );
  }

  if (!user) return null;

  if (!hasPermission(permission)) {
    return (
      <div className="flex min-h-[50vh] items-center justify-center">
        <Card className="max-w-md p-6 text-center">
          <div className="mx-auto flex h-11 w-11 items-center justify-center rounded-full bg-destructive/10 text-destructive">
            <LockKeyhole className="h-5 w-5" />
          </div>
          <h2 className="mt-4 text-base font-semibold">Acesso nao autorizado</h2>
          <p className="mt-2 text-sm text-muted-foreground">
            Seu perfil nao possui permissao para acessar esta area.
          </p>
        </Card>
      </div>
    );
  }

  return <>{children}</>;
}

