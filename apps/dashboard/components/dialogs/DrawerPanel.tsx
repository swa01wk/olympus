"use client";

import { Label } from "@/components/primitives";
import { useEffect, type ReactNode } from "react";

export function DrawerPanel({
  open,
  onClose,
  title,
  label,
  children,
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  label?: string;
  children: ReactNode;
}) {
  useEffect(() => {
    if (!open) return;
    const onKey = (ev: KeyboardEvent) => {
      if (ev.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div
      className="ol-scrim is-drawer"
      onMouseDown={(ev) => {
        if (ev.target === ev.currentTarget) onClose();
      }}
    >
      <aside className="ol-drawer" role="dialog" aria-modal="true" aria-label={title}>
        <header className="ol-dialog-h">
          <div>
            {label && <Label>{label}</Label>}
            <h2 className="ol-title text-base">{title}</h2>
          </div>
          <button type="button" className="ol-x" onClick={onClose} aria-label="Close">
            ×
          </button>
        </header>
        <div className="ol-dialog-b flex-1">{children}</div>
      </aside>
    </div>
  );
}
