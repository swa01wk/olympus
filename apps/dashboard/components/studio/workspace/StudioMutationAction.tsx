"use client";

import { Button } from "@/components/primitives";
import { previewStudioPost } from "@/lib/command-preview";
import { newIdempotencyKey } from "@/lib/utils";
import { isApiError } from "@/src/api/client";
import { useState } from "react";

export function StudioMutationAction({
  label,
  path,
  body,
  disabled,
  onRun,
}: {
  label: string;
  path: string;
  body?: Record<string, unknown> | null;
  disabled?: boolean;
  onRun: (idempotencyKey: string) => Promise<unknown>;
}) {
  const [armed, setArmed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [ok, setOk] = useState<string | null>(null);
  const [idem, setIdem] = useState(() => newIdempotencyKey());
  const preview = previewStudioPost(path, body, idem);

  const arm = () => {
    setIdem(newIdempotencyKey());
    setArmed(true);
  };

  const run = async () => {
    setBusy(true);
    setError(null);
    setOk(null);
    try {
      await onRun(idem);
      setOk("Command completed.");
      setArmed(false);
    } catch (e) {
      setError(isApiError(e) ? e.message : e instanceof Error ? e.message : "Request failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="ol-ws-action">
      {!armed ? (
        <Button variant="primary" disabled={disabled || busy} onClick={arm}>
          {label}
        </Button>
      ) : (
        <>
          <pre className="ol-cmd-api">{preview}</pre>
          <div className="ol-ws-action-row">
            <Button variant="primary" disabled={busy} onClick={run}>
              Confirm send
            </Button>
            <Button variant="quiet" disabled={busy} onClick={() => setArmed(false)}>
              Cancel
            </Button>
          </div>
        </>
      )}
      {ok && <p className="ol-body-sm ol-chat-ok">{ok}</p>}
      {error && (
        <p className="ol-body-sm ol-chat-err" role="alert">
          {error}
        </p>
      )}
    </div>
  );
}
