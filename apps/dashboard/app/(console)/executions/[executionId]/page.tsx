"use client";

import { useQuery } from "@tanstack/react-query";
import { useParams } from "next/navigation";
import { ExecutionWorkspace } from "@/components/execution/ExecutionWorkspace";
import { getServices } from "@/lib/api/services";
import { qk } from "@/lib/query/keys";

export default function ExecutionPage() {
  const { executionId } = useParams<{ executionId: string }>();
  const execQ = useQuery({
    queryKey: qk.execution(executionId),
    queryFn: async () => (await getServices()).executions.get(executionId),
  });

  if (!execQ.data) return <p>Loading…</p>;
  return <ExecutionWorkspace execution={execQ.data} />;
}
