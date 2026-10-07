import { cn } from "@/lib/utils";
import type { ReactNode } from "react";

export type PanelProps = {
  title?: string;
  sub?: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
  footer?: ReactNode;
  pad?: boolean;
};

export function Panel({ title, sub, actions, children, className, footer, pad = true }: PanelProps) {
  return (
    <section className={cn("ol-panel", className)}>
      {(title || actions) && (
        <header className="ol-panel-h">
          <div>
            {title && <h2 className="ol-section">{title}</h2>}
            {sub && <div className="ol-panel-sub">{sub}</div>}
          </div>
          {actions && <div className="ol-panel-actions">{actions}</div>}
        </header>
      )}
      <div className={cn("ol-panel-b", !pad && "ol-nopad")}>{children}</div>
      {footer}
    </section>
  );
}
