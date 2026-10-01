"use client";

import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";

export function EntityDrawer() {
  const search = useSearchParams();
  const router = useRouter();
  const inspect = search.get("inspect");
  if (!inspect) return null;

  const close = () => {
    const p = new URLSearchParams(search.toString());
    p.delete("inspect");
    router.push(`?${p.toString()}`, { scroll: false });
  };

  return (
    <div
      className="fixed inset-y-0 right-0 z-50 w-full max-w-md border-l border-[var(--border)] bg-[var(--surface)] p-4 shadow-xl"
      role="dialog"
      aria-label="Entity inspector"
    >
      <div className="mb-4 flex items-center justify-between">
        <h2 className="font-mono text-sm">{inspect}</h2>
        <button type="button" className="text-xs text-amber-400" onClick={close}>
          Close
        </button>
      </div>
      <p className="text-xs text-[var(--muted)]">
        Quick inspect.{" "}
        <Link href="#" className="underline" onClick={(e) => e.preventDefault()}>
          Open full page
        </Link>{" "}
        from entity links.
      </p>
    </div>
  );
}
