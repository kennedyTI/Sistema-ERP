import { Files } from "lucide-react";

export function PaperPlaceholder() {
  return (
    <section className="mx-auto flex min-h-[320px] max-w-[1100px] flex-col items-center justify-center px-5 py-10 text-center">
      <div className="flex h-12 w-12 items-center justify-center rounded-lg border border-border bg-card text-primary shadow-sm">
        <Files className="h-6 w-6" />
      </div>
      <h2 className="mt-5 text-base font-semibold">Módulo em desenvolvimento</h2>
      <p className="mt-2 max-w-xl text-sm leading-6 text-muted-foreground">
        A funcionalidade de papel será implementada nas próximas etapas do módulo Impressoras.
      </p>
    </section>
  );
}
