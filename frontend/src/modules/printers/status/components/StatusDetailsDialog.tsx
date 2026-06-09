import { useEffect, useState } from "react";
import { Activity, Loader2, Printer } from "lucide-react";

import {
  fetchPrinterStatusDetail,
  fetchPrinterStatusLogs,
  type PrinterOperationalLog,
  type PrinterOperationalStatus,
} from "@/modules/printers/status/statusApi";
import { Alert, AlertDescription, AlertTitle } from "@/shared/ui/alert";
import { Badge } from "@/shared/ui/badge";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/shared/ui/dialog";
import { ScrollArea } from "@/shared/ui/scroll-area";
import { Separator } from "@/shared/ui/separator";
import { cn } from "@/shared/lib/utils";

const statusLabels = {
  desconhecido: "Desconhecido",
  online: "Online",
  offline: "Offline",
  erro: "Erro",
} as const;

const alertDotStyles = {
  cinza: "bg-muted-foreground",
  verde: "bg-emerald-500",
  amarelo: "bg-amber-400",
  vermelho: "bg-red-500",
} as const;

export function StatusDetailsDialog({
  status,
  open,
  onOpenChange,
}: {
  status: PrinterOperationalStatus | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const [details, setDetails] = useState<PrinterOperationalStatus | null>(null);
  const [logs, setLogs] = useState<PrinterOperationalLog[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open || !status) return;

    let active = true;
    setDetails(status);
    setLogs([]);
    setError(null);
    setLoading(true);

    void Promise.all([
      fetchPrinterStatusDetail(status.machine_id),
      fetchPrinterStatusLogs(status.machine_id),
    ])
      .then(([detail, recentLogs]) => {
        if (!active) return;
        setDetails(detail);
        setLogs(recentLogs);
      })
      .catch((err) => {
        if (!active) return;
        setError(err instanceof Error ? err.message : "Nao foi possivel carregar os detalhes.");
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
    };
  }, [open, status]);

  const current = details ?? status;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[92vh] max-w-5xl overflow-hidden">
        <DialogHeader>
          <DialogTitle>Detalhes da impressora</DialogTitle>
          <DialogDescription>
            Consulta operacional e eventos recentes. Nenhuma alteração pode ser feita nesta tela.
          </DialogDescription>
        </DialogHeader>

        {!current ? null : (
          <ScrollArea className="max-h-[76vh] pr-4">
            <div className="space-y-6">
              <div className="grid gap-5 lg:grid-cols-[180px_1fr]">
                <div className="flex min-h-36 flex-col items-center justify-center rounded-lg border border-dashed border-border bg-muted/35 text-center">
                  <Printer className="h-10 w-10 text-muted-foreground" />
                  <p className="mt-3 text-sm font-medium">Imagem do modelo</p>
                  <p className="mt-1 text-xs text-muted-foreground">Disponível em etapa futura</p>
                </div>

                <div className="space-y-4">
                  <div className="flex flex-wrap items-center gap-3">
                    <Badge variant="outline">{statusLabels[current.status_operacional]}</Badge>
                    <span className="inline-flex items-center gap-2 text-sm capitalize">
                      <span className={cn("h-2.5 w-2.5 rounded-full", alertDotStyles[current.nivel_alerta])} />
                      {current.nivel_alerta}
                    </span>
                  </div>
                  <div>
                    <h3 className="text-xl font-semibold">{current.machine_name}</h3>
                    <p className="mt-1 text-sm text-muted-foreground">{current.ip_address}</p>
                  </div>
                  <div className="grid gap-3 sm:grid-cols-2">
                    <Detail label="Alerta" value={current.mensagem_alerta} />
                    <Detail label="Mensagem" value={current.mensagem_operador} />
                  </div>
                </div>
              </div>

              {loading && (
                <div className="flex items-center gap-2 text-sm text-muted-foreground">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Carregando detalhes e últimos logs...
                </div>
              )}

              {error && (
                <Alert variant="destructive">
                  <AlertTitle>Detalhes incompletos</AlertTitle>
                  <AlertDescription>{error}</AlertDescription>
                </Alert>
              )}

              <Separator />

              <section>
                <h3 className="text-sm font-semibold">Informações da impressora</h3>
                <div className="mt-3 grid gap-x-6 gap-y-4 sm:grid-cols-2 lg:grid-cols-3">
                  <Detail label="Local" value={current.sector} />
                  <Detail label="Fabricante" value={current.manufacturer} />
                  <Detail label="Modelo" value={current.model} />
                  <Detail label="Centro de custo" value={current.cost_center} />
                  <Detail label="Última atualização" value={formatFullDateTime(current.ultima_verificacao_em)} />
                  <Detail label="Último sucesso" value={formatFullDateTime(current.ultimo_sucesso_em)} />
                  <Detail label="Última falha" value={formatFullDateTime(current.ultima_falha_em)} />
                  <Detail
                    label="Tempo de resposta"
                    value={current.tempo_resposta_ms === null ? null : `${current.tempo_resposta_ms} ms`}
                  />
                  <Detail label="Origem" value={current.origem} />
                </div>
              </section>

              <Separator />

              <section>
                <h3 className="text-sm font-semibold">Resposta técnica</h3>
                <pre className="mt-3 max-h-44 overflow-auto whitespace-pre-wrap rounded-lg border border-border bg-muted/40 p-4 text-xs text-muted-foreground">
                  {current.resposta_bruta ?? "Nenhuma resposta técnica registrada."}
                </pre>
              </section>

              <Separator />

              <section>
                <div className="flex items-center gap-2">
                  <Activity className="h-4 w-4 text-primary" />
                  <h3 className="text-sm font-semibold">Últimos logs</h3>
                </div>
                {logs.length === 0 ? (
                  <p className="mt-3 text-sm text-muted-foreground">Nenhum evento operacional registrado.</p>
                ) : (
                  <div className="mt-3 divide-y divide-border rounded-lg border border-border">
                    {logs.map((log) => (
                      <div key={log.id} className="grid gap-2 px-4 py-3 sm:grid-cols-[180px_1fr_auto] sm:items-center">
                        <div>
                          <p className="text-sm font-medium">{formatEventType(log.tipo_evento)}</p>
                          <p className="text-xs text-muted-foreground">{log.origem}</p>
                        </div>
                        <div className="text-sm">
                          <p>{log.mensagem ?? "Evento sem mensagem."}</p>
                          <p className="mt-1 text-xs text-muted-foreground">
                            {formatTransition(log.status_anterior, log.status_novo)}
                          </p>
                        </div>
                        <time className="text-xs text-muted-foreground">{formatFullDateTime(log.verificado_em)}</time>
                      </div>
                    ))}
                  </div>
                )}
              </section>
            </div>
          </ScrollArea>
        )}
      </DialogContent>
    </Dialog>
  );
}

function Detail({ label, value }: { label: string; value: string | null | undefined }) {
  return (
    <div>
      <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{label}</p>
      <p className="mt-1 text-sm">{value || "-"}</p>
    </div>
  );
}

function formatFullDateTime(value: string | null) {
  if (!value) return "Sem registro";
  return new Intl.DateTimeFormat("pt-BR", {
    dateStyle: "short",
    timeStyle: "medium",
  }).format(new Date(value));
}

function formatEventType(value: string) {
  return value.replaceAll("_", " ").replace(/^\w/, (letter) => letter.toUpperCase());
}

function formatTransition(previous: string | null, next: string | null) {
  if (!previous && !next) return "Sem alteração de estado.";
  return `${previous ?? "-"} → ${next ?? "-"}`;
}
