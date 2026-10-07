"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useCallback, useState } from "react";
import { isApiError } from "@/src/api/client";
import { getAccessToken, getApiBaseUrl, setAccessToken } from "@/src/api/config";
import { queryKeys } from "@/src/api/query-keys";
import { Button } from "@/components/primitives/Button";
import { EmptyState } from "@/components/primitives/EmptyState";

function errorHint(error: unknown): { title: string; description: string } {
  if (isApiError(error)) {
    if (error.status === 401) {
      return {
        title: "Sign in required",
        description: "Paste a Control API bearer token below, or set NEXT_PUBLIC_OLYMPUS_API_TOKEN in apps/dashboard/.env.local.",
      };
    }
    return {
      title: "Could not reach Control API",
      description: `${error.code}: ${error.message}`,
    };
  }
  return {
    title: "Control API unavailable",
    description: `Start the API (uv run uvicorn apps.control_api.main:app --reload) and confirm ${getApiBaseUrl()}/health responds.`,
  };
}

export function DevApiSignIn({ error }: { error?: unknown }) {
  const queryClient = useQueryClient();
  const [draft, setDraft] = useState(() => getAccessToken() ?? "");
  const hint = error ? errorHint(error) : errorHint(null);

  const save = useCallback(() => {
    const trimmed = draft.trim();
    setAccessToken(trimmed || null);
    void queryClient.invalidateQueries({ queryKey: queryKeys.projects.all });
    void queryClient.invalidateQueries({ queryKey: queryKeys.actor });
  }, [draft, queryClient]);

  return (
    <EmptyState title={hint.title} description={hint.description}>
      <div className="flex flex-col gap-3 max-w-md w-full mt-2">
        <label className="flex flex-col gap-1 text-sm text-left">
          <span className="ol-muted">API base</span>
          <code className="text-xs">{getApiBaseUrl()}</code>
        </label>
        <label className="flex flex-col gap-1 text-sm text-left">
          <span className="ol-muted">Bearer token</span>
          <input
            className="w-full h-9 px-3 rounded-md border border-[var(--border-strong)] bg-[var(--surface)] font-mono text-xs"
            type="password"
            autoComplete="off"
            spellCheck={false}
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            placeholder="olympus_…"
          />
        </label>
        <Button variant="primary" type="button" onClick={save}>
          Save token
        </Button>
        <p className="ol-muted text-xs m-0 text-left">
          Generate a token:{" "}
          <code className="text-[0.7rem]">
            uv run python -m apps.control_api.cli.seed_actor --name dev --roles OPERATOR,APPROVER
          </code>
        </p>
      </div>
    </EmptyState>
  );
}
