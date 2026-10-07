"use client";

import { Label } from "@/components/primitives";
import { cn } from "@/lib/utils";
import { useEffect, useRef, type ReactNode } from "react";

export function ModalDialog({
  open,
  onClose,
  title,
  label,
  children,
  footer,
  wide,
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  label?: string;
  children: ReactNode;
  footer?: ReactNode;
  wide?: boolean;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const prevFocus = useRef<HTMLElement | null>(null);

  useEffect(() => {
    if (!open) return;
    prevFocus.current = document.activeElement as HTMLElement | null;
    const el = ref.current;
    const focusable = el?.querySelector<HTMLElement>(
      "textarea, input, select, button:not([disabled])",
    );
    focusable?.focus();

    const onKey = (ev: KeyboardEvent) => {
      if (ev.key === "Escape") onClose();
      if (ev.key === "Tab" && el) {
        const all = Array.from(
          el.querySelectorAll("button:not([disabled]), textarea, input, select"),
        ) as HTMLElement[];
        if (!all.length) return;
        const first = all[0];
        const last = all[all.length - 1];
        if (ev.shiftKey && document.activeElement === first) {
          ev.preventDefault();
          last.focus();
        } else if (!ev.shiftKey && document.activeElement === last) {
          ev.preventDefault();
          first.focus();
        }
      }
    };
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("keydown", onKey);
      prevFocus.current?.focus?.();
    };
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div
      className="ol-scrim"
      onMouseDown={(ev) => {
        if (ev.target === ev.currentTarget) onClose();
      }}
    >
      <div
        ref={ref}
        className={cn("ol-dialog", wide && "is-wide")}
        role="dialog"
        aria-modal="true"
        aria-labelledby="ol-dlg-title"
      >
        <header className="ol-dialog-h">
          <div>
            {label && <Label>{label}</Label>}
            <h2 id="ol-dlg-title" className="ol-title text-base">
              {title}
            </h2>
          </div>
          <button type="button" className="ol-x" onClick={onClose} aria-label="Close">
            ×
          </button>
        </header>
        <div className="ol-dialog-b">{children}</div>
        {footer && <footer className="ol-dialog-f">{footer}</footer>}
      </div>
    </div>
  );
}
