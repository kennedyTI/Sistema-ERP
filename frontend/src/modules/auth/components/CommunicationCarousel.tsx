import { useEffect, useState } from "react";

import { cn } from "@/shared/lib/utils";

const slides = [
  "/static/imgs/communications/comunicado-01.png",
  "/static/imgs/communications/comunicado-02.png",
  "/static/imgs/communications/comunicado-03.png",
  "/static/imgs/communications/comunicado-04.png",
];

export function CommunicationCarousel() {
  const [available, setAvailable] = useState<string[]>([]);
  const [index, setIndex] = useState(0);

  useEffect(() => {
    let cancelled = false;

    Promise.all(
      slides.map(
        (src) =>
          new Promise<string | null>((resolve) => {
            const img = new Image();
            img.onload = () => resolve(src);
            img.onerror = () => resolve(null);
            img.src = src;
          }),
      ),
    ).then((result) => {
      if (!cancelled) setAvailable(result.filter((src): src is string => Boolean(src)));
    });

    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (available.length < 2) return;
    const timer = window.setInterval(() => {
      setIndex((current) => (current + 1) % available.length);
    }, 6000);

    return () => window.clearInterval(timer);
  }, [available.length]);

  if (available.length === 0) {
    return (
      <div className="flex h-full min-h-[360px] w-full items-center justify-center p-10 text-center">
        <div className="max-w-xs">
          <p className="text-sm font-medium text-primary">Comunicados oficiais</p>
          <p className="mt-2 text-xs text-muted-foreground">Nenhum comunicado disponivel no momento.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-full min-h-[420px] w-full flex-col">
      <p className="mb-4 text-[11px] font-medium uppercase tracking-[0.18em] text-primary/80">
        Comunicados oficiais
      </p>
      <div className="relative flex-1 overflow-visible">
        {available.map((src, slideIndex) => (
          <img
            key={src}
            src={src}
            alt={`Comunicado ${slideIndex + 1}`}
            loading={slideIndex === 0 ? "eager" : "lazy"}
            className={cn(
              "absolute inset-0 h-full w-full rounded-2xl object-contain transition-[opacity,transform,filter] duration-1000 ease-in-out will-change-[opacity,transform]",
              "drop-shadow-[0_26px_44px_rgba(0,63,125,0.22)] dark:drop-shadow-[0_28px_48px_rgba(0,0,0,0.45)]",
              slideIndex === index ? "scale-100 opacity-100 blur-0" : "pointer-events-none scale-[0.985] opacity-0 blur-[1px]",
            )}
          />
        ))}
      </div>
      {available.length > 1 && (
        <div className="mt-5 flex items-center justify-center gap-2">
          {available.map((_, slideIndex) => (
            <button
              key={slideIndex}
              type="button"
              aria-label={`Ir para o comunicado ${slideIndex + 1}`}
              onClick={() => setIndex(slideIndex)}
              onFocus={() => setIndex(slideIndex)}
              onMouseEnter={() => setIndex(slideIndex)}
              className={cn(
                "h-2 rounded-full transition-all duration-300",
                slideIndex === index ? "w-8 bg-primary" : "w-2 bg-primary/25 hover:bg-primary/50",
              )}
            />
          ))}
        </div>
      )}
    </div>
  );
}

