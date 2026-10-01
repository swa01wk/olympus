"use client";

import { useQuery } from "@tanstack/react-query";
import { useParams } from "next/navigation";
import { StatusBadge } from "@/components/status/StatusBadge";
import { getServices } from "@/lib/api/services";

export default function IcDetailPage() {
  const { icId } = useParams<{ icId: string }>();
  const q = useQuery({
    queryKey: ["ic", icId],
    queryFn: async () => (await getServices()).integration.get(icId),
  });
  const ic = q.data;
  if (!ic) return <p>Loading…</p>;
  return (
    <div>
      <h1 className="font-mono text-xl">{ic.key}</h1>
      <StatusBadge value={ic.status} />
      <p className="mt-2 font-mono text-xs">base: {ic.base_sha}</p>
      <p className="font-mono text-xs">integrated: {ic.integrated_sha ?? "—"}</p>
    </div>
  );
}
