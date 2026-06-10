import { GripVertical } from "lucide-react";

export function ColumnDragPreview({
  label,
  position,
}: {
  label: string | null;
  position: { x: number; y: number } | null;
}) {
  if (!label || !position) return null;

  return (
    <div
      className="pointer-events-none fixed z-[80] inline-flex items-center gap-2 rounded-md border border-primary/50 bg-popover px-3 py-2 text-sm font-medium text-popover-foreground shadow-lg"
      style={{ left: position.x + 14, top: position.y + 14 }}
      aria-hidden="true"
    >
      <GripVertical className="h-4 w-4 text-primary" />
      {label}
    </div>
  );
}
