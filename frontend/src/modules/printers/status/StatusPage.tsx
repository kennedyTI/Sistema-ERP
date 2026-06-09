import { useEffect, useMemo, useState } from "react";
import { Activity, CircleAlert, Loader2, RefreshCw } from "lucide-react";

import { RequireAuth } from "@/modules/auth/RequireAuth";
import {
  fetchPrinterStatuses,
  type AlertLevel,
  type OperationalStatus,
  type PrinterOperationalStatus,
} from "@/modules/printers/status/statusApi";
import { Alert, AlertDescription, AlertTitle } from "@/shared/ui/alert";
import { Badge } from "@/shared/ui/badge";
import { Button } from "@/shared/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/shared/ui/table";
import { cn } from "@/shared/lib/utils";

const statusLabels: Record<OperationalStatus, string> = {
  desconhecido: "Desconhecido",
  online: "Online",
  offline: "Offline",
  erro: "Erro",
};

const statusStyles: Record<OperationalStatus, string> = {
  desconhecido: "border-muted-foreground/30 bg-muted text-muted-foreground",
  online: "border-emerald-500/30 bg-emerald-500/12 text-emerald-700 dark:text-emerald-300",
  offline: "border-red-500/30 bg-red-500/12 text-red-700 dark:text-red-300",
  erro: "border-orange-500/30 bg-orange-500/12 text-orange-700 dark:text-orange-300",
};

const alertStyles: Record<AlertLevel, string> = {
  cinza: "bg-muted-foreground",
  verde: "bg-emerald-500",
  amarelo: "bg-amber-400",
  vermelho: "bg-red-500",
};

export function StatusPage() {
  return (
    <RequireAuth permission="can_access_printers_status">
      <StatusContent />
    </RequireAuth>
  );
}

function StatusContent() {
  const [statuses, setStatuses] = useState<PrinterOperationalStatus[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const onlineCount = useMemo(
    () => statuses.filter((status) => status.status_operacional === "online").length,
    [statuses],
  );
  const attentionCount = useMemo(
    () => statuses.filter((status) => ["amarelo", "vermelho"].includes(status.nivel_alerta)).length,
    [statuses],
  );

  async function loadStatuses() {
    setLoading(true);
    setError(null);
    try {
      setStatuses(await fetchPrinterStatuses());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Nao foi possivel carregar os status.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadStatuses();
  }, []);

  return (
    <div className="mx-auto flex max-w-[1380px] flex-col gap-5">
      <section className="rounded-lg border border-border/70 bg-card px-6 py-6 shadow-[var(--shadow-card)]">
        <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
          <div>
            <p className="text-xs font-medium uppercase tracking-wide text-primary">Impressoras</p>
            <h1 className="mt-2 text-2xl font-semibold tracking-tight">Status</h1>
            <p className="mt-2 max-w-2xl text-sm text-muted-foreground">
              Consulta do estado operacional atual das impressoras cadastradas.
            </p>
          </div>
          <Button type="button" variant="outline" onClick={loadStatuses} disabled={loading}>
            {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
            Atualizar
          </Button>
        </div>

        <div className="mt-5 flex flex-wrap gap-2 text-sm">
          <Badge variant="secondary">{statuses.length} impressora(s)</Badge>
          <Badge variant="outline">{onlineCount} online</Badge>
          <Badge variant="outline">{attentionCount} com alerta</Badge>
        </div>
      </section>

      {error && (
        <Alert variant="destructive">
          <AlertTitle>Erro ao consultar status</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      <section className="overflow-hidden rounded-lg border border-border/70 bg-card shadow-[var(--shadow-card)]">
        {loading ? (
          <div className="flex min-h-64 items-center justify-center text-sm text-muted-foreground">
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            Carregando status...
          </div>
        ) : statuses.length === 0 ? (
          <div className="flex min-h-64 flex-col items-center justify-center px-6 text-center">
            <Activity className="h-9 w-9 text-muted-foreground" />
            <h2 className="mt-4 text-base font-semibold">Nenhum status disponivel</h2>
            <p className="mt-2 max-w-md text-sm text-muted-foreground">
              Os status operacionais aparecerao aqui quando houver impressoras cadastradas.
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto p-4">
            <Table className="min-w-[1180px]">
              <TableHeader>
                <TableRow>
                  <TableHead>Maquina</TableHead>
                  <TableHead>IP</TableHead>
                  <TableHead>Fabricante</TableHead>
                  <TableHead>Modelo</TableHead>
                  <TableHead>Setor</TableHead>
                  <TableHead>Status operacional</TableHead>
                  <TableHead>Alerta</TableHead>
                  <TableHead>Ultima verificacao</TableHead>
                  <TableHead>Mensagem</TableHead>
                  <TableHead className="text-right">Resposta</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {statuses.map((status) => (
                  <TableRow key={status.machine_id} className="hover:bg-primary/10 dark:hover:bg-primary/20">
                    <TableCell className="font-medium">{status.machine_name}</TableCell>
                    <TableCell>{status.ip_address}</TableCell>
                    <TableCell>{status.manufacturer ?? "-"}</TableCell>
                    <TableCell>{status.model ?? "-"}</TableCell>
                    <TableCell>{status.sector ?? "-"}</TableCell>
                    <TableCell>
                      <Badge variant="outline" className={statusStyles[status.status_operacional]}>
                        {statusLabels[status.status_operacional]}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <span className="inline-flex items-center gap-2 capitalize">
                        <span
                          className={cn("h-2.5 w-2.5 rounded-full", alertStyles[status.nivel_alerta])}
                          aria-hidden="true"
                        />
                        {status.nivel_alerta}
                      </span>
                    </TableCell>
                    <TableCell>{formatDateTime(status.ultima_verificacao_em)}</TableCell>
                    <TableCell className="max-w-[260px] whitespace-normal">
                      {status.mensagem_alerta ?? "-"}
                    </TableCell>
                    <TableCell className="text-right">
                      {status.tempo_resposta_ms === null ? "-" : `${status.tempo_resposta_ms} ms`}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}
      </section>

      {!loading && attentionCount > 0 && (
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <CircleAlert className="h-4 w-4 text-amber-500" />
          Existem impressoras que exigem atencao operacional.
        </div>
      )}
    </div>
  );
}

function formatDateTime(value: string | null) {
  if (!value) return "Ainda nao verificada";
  return new Intl.DateTimeFormat("pt-BR", {
    dateStyle: "short",
    timeStyle: "medium",
  }).format(new Date(value));
}
