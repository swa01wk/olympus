"use client";

import Link from "next/link";

export function RunningNotice({ executionId, label }: { executionId: string; label?: string }) {
  return (
    <p className="ol-ws-running" role="status">
      Running — {label ?? executionId}{" "}
      <Link className="ol-chat-link" href={`/executions/${executionId}`}>
        View execution
      </Link>
    </p>
  );
}
