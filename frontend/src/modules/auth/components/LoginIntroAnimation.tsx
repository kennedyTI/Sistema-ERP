import { useEffect, useState } from "react";

import { cn } from "@/shared/lib/utils";

const LOGO_SRC = "/static/imgs/industria-logo-white.png";

export function LoginIntroAnimation({ onFinish }: { onFinish: () => void }) {
  const [phase, setPhase] = useState<"idle" | "moving" | "done">("idle");

  useEffect(() => {
    const t1 = window.setTimeout(() => setPhase("moving"), 1200);
    const t2 = window.setTimeout(() => {
      setPhase("done");
      onFinish();
    }, 2200);

    return () => {
      window.clearTimeout(t1);
      window.clearTimeout(t2);
    };
  }, [onFinish]);

  return (
    <div
      aria-hidden
      className={cn(
        "pointer-events-none fixed inset-0 z-50 flex items-center justify-center bg-primary transition-opacity duration-500",
        phase === "done" ? "opacity-0" : "opacity-100",
      )}
    >
      <img
        src={LOGO_SRC}
        alt=""
        className={cn(
          "h-24 w-auto object-contain transition-all duration-[900ms]",
          "[transition-timing-function:cubic-bezier(0.65,0,0.35,1)]",
          phase === "idle" && "scale-100 opacity-100",
          phase === "moving" && "scale-75 opacity-90",
          phase === "done" && "opacity-0",
        )}
      />
    </div>
  );
}

