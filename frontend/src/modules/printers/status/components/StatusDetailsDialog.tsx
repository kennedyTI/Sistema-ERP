import { useEffect, useState } from "react";
import { Activity, Loader2 } from "lucide-react";

import { PrinterModelImage } from "@/modules/printers/shared/PrinterModelImage";
import { selectHighestSeverityAlerts } from "@/modules/printers/status/alertSelection";
import {
  fetchPrinterStatusDetail,
  fetchPrinterStatusLogs,
  type AlertLevel,
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
  online: "Online",
  offline: "Offline",
} as const;

const methodLabels = {
  icmp: "ICMP",
  tcp: "TCP",
  snmp: "SNMP",
  html: "HTML/HTTP",
  fallback: "Fallback",
} as const;

const alertDotStyles = {
  cinza: "bg-muted-foreground",
  verde: "bg-emerald-500",
  amarelo: "bg-amber-400",
  vermelho: "bg-red-500",
} as const;

const statusBadgeStyles = {
  online: "border-emerald-500/30 bg-emerald-500/12 text-emerald-700 dark:text-emerald-300",
  offline: "border-red-500/30 bg-red-500/12 text-red-700 dark:text-red-300",
} as const;

const alertPillStyles: Record<AlertLevel, string> = {
  cinza: "border-muted-foreground/30 bg-muted/70 text-muted-foreground",
  verde: "border-emerald-500/30 bg-emerald-500/12 text-emerald-700 dark:text-emerald-300",
  amarelo: "border-amber-400/40 bg-amber-500/12 text-amber-700 dark:text-amber-300",
  vermelho: "border-red-500/30 bg-red-500/12 text-red-700 dark:text-red-300",
};

const ALERT_ROTATION_INTERVAL_MS = 4_000;

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
  const [alertRotationIndex, setAlertRotationIndex] = useState(0);

  // ---------------------------------------------------------------------------
  // 📌 MODAL ESTRITAMENTE CONSULTIVO
  // ---------------------------------------------------------------------------
  // Detalhe e logs são carregados em paralelo. O flag active evita atualizar
  // estado após fechar o modal ou trocar rapidamente de impressora.
  useEffect(() => {
    if (!open || !status) return;

    let active = true;
    setDetails(status);
    setLogs([]);
    setError(null);
    setLoading(true);
    setAlertRotationIndex(0);

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
  const displayAlerts = current ? selectHighestSeverityAlerts(current) : [];
  const visibleAlert = displayAlerts.length
    ? displayAlerts[alertRotationIndex % displayAlerts.length]
    : null;

  useEffect(() => {
    if (!open || displayAlerts.length <= 1) return;
    const intervalId = window.setInterval(() => {
      setAlertRotationIndex((currentIndex) => currentIndex + 1);
    }, ALERT_ROTATION_INTERVAL_MS);

    return () => window.clearInterval(intervalId);
  }, [displayAlerts.length, open]);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="h-[min(92dvh,780px)] max-w-[1180px] grid-rows-[auto_minmax(0,1fr)] gap-0 overflow-hidden p-0">
        <div className="border-b border-border px-4 py-3.5 pr-14 sm:px-5 sm:py-4">
          <DialogHeader>
            <DialogTitle>Detalhes da impressora</DialogTitle>
            <DialogDescription>
              Consulta operacional e eventos recentes. Nenhuma alteração pode ser feita nesta tela.
            </DialogDescription>
          </DialogHeader>
        </div>

        {!current ? null : (
          <ScrollArea className="min-h-0">
            <div className="space-y-4 px-4 py-3.5 sm:px-5 sm:py-4">
              <div className="grid gap-4 lg:grid-cols-[280px_minmax(0,1fr)]">
                <PrinterModelImage
                  imageUrl={current.url_imagem}
                  model={current.model}
                  equipmentName={current.machine_name}
                />

                <div className="space-y-4">
                  <div>
                    <p className="text-xs font-medium uppercase text-muted-foreground">
                      Nome da máquina
                    </p>
                    <h3 className="mt-1 text-xl font-semibold">{current.machine_name}</h3>
                    <p className="mt-1 text-sm text-muted-foreground">{current.ip_address}</p>
                  </div>
                  <div className="grid gap-x-6 gap-y-4 sm:grid-cols-2 lg:grid-cols-3">
                    <Detail label="Fabricante" value={current.manufacturer} />
                    <Detail label="Modelo" value={current.model} />
                    <Detail label="Setor" value={current.sector} />
                    <Detail label="Centro de custo" value={current.cost_center} />
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
                <div className="flex items-center gap-2">
                  <Activity className="h-4 w-4 text-primary" />
                  <h3 className="text-sm font-semibold">Estado operacional</h3>
                </div>
                <div className="mt-3 grid gap-x-6 gap-y-4 sm:grid-cols-2 lg:grid-cols-4">
                  <div>
                    <p className="text-xs font-medium uppercase text-muted-foreground">
                      Status operacional
                    </p>
                    <Badge
                      variant="outline"
                      className={cn("mt-2", statusBadgeStyles[current.status_operacional])}
                    >
                      {statusLabels[current.status_operacional]}
                    </Badge>
                  </div>
                  <div>
                    <p className="text-xs font-medium uppercase text-muted-foreground">Alerta</p>
                    {visibleAlert ? (
                      <span
                        className={cn(
                          "mt-2 inline-flex max-w-full items-center gap-2 rounded-full border px-2.5 py-1 text-sm font-medium",
                          alertPillStyles[visibleAlert.nivel_alerta],
                        )}
                        title={displayAlerts.map((alert) => alert.mensagem).join(" | ")}
                      >
                        <span
                          className={cn(
                            "h-2.5 w-2.5 shrink-0 rounded-full",
                            alertDotStyles[visibleAlert.nivel_alerta],
                          )}
                          aria-hidden="true"
                        />
                        <span className="min-w-0 truncate">{visibleAlert.mensagem}</span>
                        {displayAlerts.length > 1 && (
                          <span className="rounded-full border border-current/25 px-1.5 py-0.5 text-[10px] leading-none opacity-80">
                            {(alertRotationIndex % displayAlerts.length) + 1}/{displayAlerts.length}
                          </span>
                        )}
                      </span>
                    ) : (
                      <p className="mt-1 text-sm">-</p>
                    )}
                  </div>
                  <Detail label="Mensagem operacional" value={current.mensagem_operador} />
                  <Detail
                    label="Última verificação"
                    value={formatFullDateTime(current.ultima_verificacao_em)}
                  />
                  <Detail
                    label="Último sucesso"
                    value={formatFullDateTime(current.ultimo_sucesso_em)}
                  />
                  <Detail
                    label="Última falha"
                    value={formatFullDateTime(current.ultima_falha_em)}
                  />
                  <Detail
                    label="Tempo de resposta"
                    value={
                      current.tempo_resposta_ms === null ? null : `${current.tempo_resposta_ms} ms`
                    }
                  />
                  <Detail
                    label="Método de confirmação"
                    value={
                      current.metodo_confirmacao
                        ? methodLabels[current.metodo_confirmacao]
                        : null
                    }
                  />
                  <Detail label="Origem" value={current.origem} />
                </div>
              </section>

              <Separator />

              <section>
                <div className="flex items-center gap-2">
                  <Activity className="h-4 w-4 text-primary" />
                  <h3 className="text-sm font-semibold">
                    Últimos logs das últimas 24h
                  </h3>
                </div>
                {logs.length === 0 ? (
                  <p className="mt-3 text-sm text-muted-foreground">
                    Nenhum evento operacional registrado nas últimas 24h.
                  </p>
                ) : (
                  <div className="mt-3 divide-y divide-border rounded-lg border border-border">
                    {logs.slice(0, 10).map((log) => (
                      <div
                        key={log.id}
                        className="grid gap-1.5 px-4 py-3 sm:grid-cols-[150px_minmax(0,1fr)] sm:items-center sm:gap-4"
                      >
                        <time className="text-xs text-muted-foreground">
                          {formatEventDateTime(log.data_hora)}
                        </time>
                        <p className="min-w-0 text-sm">
                          {log.mensagem}
                          <span className="ml-2 text-xs text-muted-foreground">
                            ({log.origem})
                          </span>
                        </p>
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

function formatEventDateTime(value: string) {
  return new Intl.DateTimeFormat("pt-BR", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}
