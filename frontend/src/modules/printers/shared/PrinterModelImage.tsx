import { useEffect, useState } from "react";
import { ImageOff } from "lucide-react";

import { cn } from "@/shared/lib/utils";

export function PrinterModelImage({
  imageUrl,
  model,
  equipmentName,
  className,
}: {
  imageUrl: string | null | undefined;
  model: string | null;
  equipmentName: string;
  className?: string;
}) {
  const [imageUnavailable, setImageUnavailable] = useState(false);

  useEffect(() => {
    setImageUnavailable(false);
  }, [imageUrl]);

  const frameClassName = cn(
    "flex aspect-[4/3] min-h-[210px] max-h-[280px] w-full items-center justify-center overflow-hidden rounded-lg border border-border bg-card sm:min-h-[230px]",
    className,
  );

  if (!imageUrl || imageUnavailable) {
    return (
      <div className={cn(frameClassName, "flex-col border-dashed bg-muted/30 px-4 text-center")}>
        <ImageOff className="h-10 w-10 text-muted-foreground" aria-hidden="true" />
        <p className="mt-3 text-sm font-medium">Imagem não disponível</p>
        <p className="mt-1 text-xs text-muted-foreground">{model ?? "Modelo não informado"}</p>
      </div>
    );
  }

  return (
    <div className={cn(frameClassName, "bg-white p-1.5 sm:p-2")}>
      <img
        src={imageUrl}
        alt={`Modelo ${model ?? ""} de ${equipmentName}`}
        className="h-full w-full object-contain object-center"
        onError={() => setImageUnavailable(true)}
      />
    </div>
  );
}
