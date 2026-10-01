"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { getServices } from "@/lib/api/services";
import { qk } from "@/lib/query/keys";
import { newIdempotencyKey } from "@/lib/utils";

export default function InboxPage() {
  const qc = useQueryClient();
  const inboxQ = useQuery({
    queryKey: qk.inbox(),
    queryFn: async () => (await getServices()).inbox.list(),
  });
  const actorQ = useQuery({
    queryKey: qk.actor(),
    queryFn: async () => (await getServices()).auth.me(),
  });

  const decide = useMutation({
    mutationFn: async (args: { id: string; decision: string }) => {
      const svc = await getServices();
      return svc.approvals.decide(args.id, args.decision, "UI decision", newIdempotencyKey());
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: qk.inbox() });
      qc.invalidateQueries({ queryKey: qk.approvals() });
    },
  });

  const viewer = actorQ.data?.roles.includes("VIEWER");

  return (
    <div>
      <h1 className="mb-2 text-xl font-semibold">Human Attention Center</h1>
      <p className="mb-4 text-xs text-[var(--muted)]">
        Approval is recorded only through this form; chat acknowledgement does not count as approval.
      </p>
      <ul className="space-y-3">
        {inboxQ.data?.map((item) => (
          <li key={item.id} className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-4">
            <div className="font-medium">{item.title}</div>
            <div className="text-sm text-[var(--muted)]">{item.why}</div>
            <div className="mt-3 flex gap-2">
              <Button
                size="sm"
                disabled={viewer || decide.isPending}
                onClick={() => decide.mutate({ id: item.id, decision: "APPROVED" })}
              >
                Approve
              </Button>
              <Button
                size="sm"
                variant="outline"
                disabled={viewer || decide.isPending}
                onClick={() => decide.mutate({ id: item.id, decision: "CHANGES_REQUESTED" })}
              >
                Request Changes
              </Button>
              <Button
                size="sm"
                variant="outline"
                disabled={viewer || decide.isPending}
                onClick={() => decide.mutate({ id: item.id, decision: "REJECTED" })}
              >
                Reject
              </Button>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
