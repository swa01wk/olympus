"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Command } from "cmdk";
import { useQuery } from "@tanstack/react-query";
import { getServices } from "@/lib/api/services";
import { qk } from "@/lib/query/keys";

export function CommandPalette({ projectId }: { projectId: string }) {
  const [open, setOpen] = useState(false);
  const router = useRouter();
  const cyclesQ = useQuery({
    queryKey: qk.cycles(projectId),
    queryFn: async () => (await getServices()).deliveryCycles.list(projectId),
  });

  useEffect(() => {
    const down = (e: KeyboardEvent) => {
      if (e.key === "k" && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        setOpen((o) => !o);
      }
    };
    window.addEventListener("keydown", down);
    return () => window.removeEventListener("keydown", down);
  }, []);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center bg-black/60 pt-[20vh]" role="presentation">
      <Command
        className="w-full max-w-lg overflow-hidden rounded-lg border border-[var(--border)] bg-[var(--surface)] shadow-xl"
        label="Command palette"
      >
        <Command.Input placeholder="Jump to cycle or route…" className="w-full border-b border-[var(--border)] bg-transparent px-3 py-2 text-sm outline-none" />
        <Command.List className="max-h-72 overflow-auto p-2">
          <Command.Empty className="py-4 text-center text-xs text-[var(--muted)]">No matches.</Command.Empty>
          <Command.Group heading="Delivery cycles">
            {cyclesQ.data?.map((c) => (
              <Command.Item
                key={c.id}
                className="cursor-pointer rounded px-2 py-1.5 text-sm aria-selected:bg-white/10"
                onSelect={() => {
                  router.push(`/projects/${projectId}?cycle=${c.id}`);
                  setOpen(false);
                }}
              >
                {c.key} — {c.objective}
              </Command.Item>
            ))}
          </Command.Group>
          <Command.Group heading="Routes">
            <Command.Item
              className="cursor-pointer rounded px-2 py-1.5 text-sm aria-selected:bg-white/10"
              onSelect={() => {
                router.push(`/projects/${projectId}/code`);
                setOpen(false);
              }}
            >
              Code Intelligence
            </Command.Item>
            <Command.Item
              className="cursor-pointer rounded px-2 py-1.5 text-sm aria-selected:bg-white/10"
              onSelect={() => {
                router.push(`/inbox?project=${projectId}`);
                setOpen(false);
              }}
            >
              Human Attention
            </Command.Item>
          </Command.Group>
        </Command.List>
      </Command>
      <button type="button" className="sr-only" onClick={() => setOpen(false)}>
        Close
      </button>
    </div>
  );
}
