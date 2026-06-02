import { useState, type FormEvent } from "react";
import { useNavigate } from "@tanstack/react-router";
import { AlertCircle, Loader2, Lock, User } from "lucide-react";

import { Button } from "@/shared/ui/button";
import { Input } from "@/shared/ui/input";
import { Label } from "@/shared/ui/label";
import { useAuth } from "@/modules/auth/authStore";
import { getDefaultPortalRoute } from "@/modules/auth/portalRoute";

const logoBlueSrc = "/static/imgs/industria-logo-blue.png";
const logoWhiteSrc = "/static/imgs/industria-logo-white.png";

export function LoginCard({ logoAnimated }: { logoAnimated: boolean }) {
  const navigate = useNavigate();
  const { login, logout } = useAuth();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);

    if (!username || !password) {
      setError("Informe usuario e senha.");
      return;
    }

    setLoading(true);
    try {
      const user = await login(username, password);
      const route = getDefaultPortalRoute(user.permissions);

      if (!route) {
        await logout();
        setError("Acesso nao autorizado. Seu perfil nao possui permissao para acessar o portal.");
        return;
      }

      await navigate({ to: route, replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Usuario ou senha invalidos.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="w-full max-w-sm">
      <div className="login-floating-card rounded-2xl border border-border/70 bg-card p-8 shadow-[0_30px_80px_-40px_rgba(0,63,125,0.35)]">
        <div className="flex h-16 items-center justify-center">
          {!logoAnimated ? (
            <div className="h-16 w-full" aria-hidden />
          ) : (
            <>
              <img
                src={logoBlueSrc}
                alt="industria"
                className="h-14 w-auto animate-fade-in object-contain dark:hidden"
              />
              <img
                src={logoWhiteSrc}
                alt="industria"
                className="hidden h-14 w-auto animate-fade-in object-contain dark:block"
              />
            </>
          )}
        </div>

        <form onSubmit={handleSubmit} className="mt-8 space-y-4">
          <div className="space-y-1.5">
            <Label htmlFor="username" className="text-xs font-medium text-muted-foreground">
              Usuario
            </Label>
            <div className="relative">
              <User className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                id="username"
                type="text"
                autoComplete="username"
                value={username}
                onChange={(event) => setUsername(event.target.value)}
                className="h-11 pl-9"
                placeholder="seu.usuario"
              />
            </div>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="password" className="text-xs font-medium text-muted-foreground">
              Senha
            </Label>
            <div className="relative">
              <Lock className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                id="password"
                type="password"
                autoComplete="current-password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                className="h-11 pl-9"
                placeholder="********"
              />
            </div>
          </div>

          <div className="min-h-[20px]">
            {error && (
              <p className="flex items-center gap-1.5 text-xs font-medium text-destructive animate-fade-in">
                <AlertCircle className="h-3.5 w-3.5" />
                {error}
              </p>
            )}
          </div>

          <Button
            type="submit"
            disabled={loading}
            className="h-11 w-full bg-primary text-base font-medium shadow-[0_8px_24px_-8px_rgba(0,91,170,0.6)] hover:bg-primary-dark"
          >
            {loading ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                Entrando...
              </>
            ) : (
              "Entrar"
            )}
          </Button>
        </form>
      </div>
    </div>
  );
}

