import Link from "next/link";
import type { ReactNode } from "react";

export function SimpleShell({
  children,
  narrow,
  showNew = true,
}: {
  children: ReactNode;
  narrow?: boolean;
  showNew?: boolean;
}) {
  return (
    <div className="sp-app">
      <header className="sp-top">
        <Link href="/" className="sp-brand">
          Olympus
        </Link>
        <span className="sp-top-spacer" />
        <Link href="/projects" className="sp-top-link">
          Inspect
        </Link>
        {showNew && (
          <Link href="/new" className="sp-btn sp-btn-primary">
            New app
          </Link>
        )}
      </header>
      <main className={narrow ? "sp-main sp-narrow" : "sp-main"}>{children}</main>
    </div>
  );
}
