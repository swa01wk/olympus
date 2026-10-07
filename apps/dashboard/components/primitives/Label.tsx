import { cn } from "@/lib/utils";
import type { ReactNode } from "react";

export function Label({ children, className }: { children: ReactNode; className?: string }) {
  return <div className={cn("ol-label", className)}>{children}</div>;
}
