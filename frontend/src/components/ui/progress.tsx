import type { HTMLAttributes } from "react";

import { cn } from "@/lib/utils";

export function Progress({
  value = 0,
  className,
  ...props
}: HTMLAttributes<HTMLDivElement> & { value?: number }) {
  const safeValue = Math.max(0, Math.min(100, value));
  return (
    <div
      className={cn("relative h-2 w-full overflow-hidden rounded-full bg-muted", className)}
      {...props}
    >
      <div
        className="h-full rounded-full bg-gradient-to-r from-primary to-success transition-all duration-300"
        style={{ width: `${safeValue}%` }}
      />
    </div>
  );
}
