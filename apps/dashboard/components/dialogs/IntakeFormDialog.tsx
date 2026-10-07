"use client";

import { ModalDialog } from "@/components/dialogs/ModalDialog";
import { Button, Label } from "@/components/primitives";
import { StudioMutationAction } from "@/components/studio/workspace/StudioMutationAction";
import {
  previewCreateCycle,
  previewPutSecret,
} from "@/lib/command-preview";
import { cn, newIdempotencyKey } from "@/lib/utils";
import {
  createDeliveryCycleCommand,
  putSecret,
  registerRepository,
  retryMaterialization,
} from "@/src/api/commands";
import { useProject } from "@/src/api/hooks/use-olympus-queries";
import {
  useProjectRepositories,
  useRepository,
  useRepositoryMaterializations,
} from "@/src/api/hooks/use-journey-queries";
import { queryKeys } from "@/src/api/query-keys";
import type { RepositoryProvider } from "@/src/api/types/repository";
import { useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";

const JOURNEYS = {
  GF: { label: "Greenfield Build", type: "GREENFIELD_BUILD" },
  BF: { label: "Brownfield Onboarding", type: "BROWNFIELD_ONBOARDING" },
  FC: { label: "Feature Change", type: "FEATURE_CHANGE" },
  BG: { label: "Bug Fix", type: "BUG_FIX" },
} as const;

type JourneyKey = keyof typeof JOURNEYS;

const PROVIDERS: RepositoryProvider[] = [
  "GITHUB",
  "GITEA",
  "GITLAB",
  "BITBUCKET",
  "LOCAL",
];

function secretNameForRepo(projectKey: string, repoName: string): string {
  return `repo-${projectKey}-${repoName}`;
}

function RepositoryMaterializationPanel({
  repositoryId,
  onRetryDone,
}: {
  repositoryId: string;
  onRetryDone: () => void;
}) {
  const repo = useRepository(repositoryId);
  const materializations = useRepositoryMaterializations(
    repo.data?.status === "ERROR" ? repositoryId : undefined,
  );
  const lastAttempt = materializations.data?.[materializations.data.length - 1];

  if (repo.isLoading && !repo.data) {
    return <p className="ol-body-sm ol-muted">Loading repository status…</p>;
  }

  const r = repo.data;
  if (!r) return null;

  return (
    <div className="ol-appr-scope" role="status">
      <div>
        <Label>Materialization</Label>
        <div>{r.status}</div>
      </div>
      {r.status_reason && (
        <div>
          <Label>Status reason</Label>
          <div className="ol-body-sm">{r.status_reason}</div>
        </div>
      )}
      {r.status === "ERROR" && lastAttempt && (
        <>
          {lastAttempt.error_class && (
            <div>
              <Label>Last error class</Label>
              <div className="ol-body-sm">{lastAttempt.error_class}</div>
            </div>
          )}
          {lastAttempt.error_detail && (
            <div>
              <Label>Last error detail</Label>
              <div className="ol-body-sm">{lastAttempt.error_detail}</div>
            </div>
          )}
          <StudioMutationAction
            label="Retry materialization"
            path={`/repositories/${repositoryId}/commands/retry_materialization`}
            onRun={async (idem) => {
              await retryMaterialization(repositoryId, idem);
              onRetryDone();
            }}
          />
        </>
      )}
      {r.status !== "READY" && r.status !== "ERROR" && (
        <p className="ol-body-sm ol-muted">Polling GET /repositories/{repositoryId} every 3 s…</p>
      )}
    </div>
  );
}

export function IntakeFormDialog({
  open,
  projectId,
  onClose,
}: {
  open: boolean;
  projectId: string | null;
  onClose: () => void;
}) {
  const router = useRouter();
  const queryClient = useQueryClient();
  const project = useProject(projectId ?? undefined);
  const repositories = useProjectRepositories(projectId ?? undefined);

  const [journey, setJourney] = useState<JourneyKey>("FC");
  const [objective, setObjective] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const [repoMode, setRepoMode] = useState<"existing" | "register">("existing");
  const [selectedRepositoryId, setSelectedRepositoryId] = useState("");
  const [activeRepositoryId, setActiveRepositoryId] = useState<string | null>(null);

  const [regName, setRegName] = useState("");
  const [regProvider, setRegProvider] = useState<RepositoryProvider>("GITHUB");
  const [regRemoteUrl, setRegRemoteUrl] = useState("");
  const [regDefaultBranch, setRegDefaultBranch] = useState("");
  const [accessToken, setAccessToken] = useState("");

  const meta = JOURNEYS[journey];
  const isBrownfield = meta.type === "BROWNFIELD_ONBOARDING";

  const trackedRepositoryId = activeRepositoryId || selectedRepositoryId || null;
  const trackedRepo = useRepository(isBrownfield ? trackedRepositoryId ?? undefined : undefined);
  const repositoryReady = trackedRepo.data?.status === "READY";

  const registerPreviewBody = useMemo(
    () => ({
      name: regName.trim(),
      provider: regProvider,
      remote_url: regRemoteUrl.trim(),
      default_branch: regDefaultBranch.trim() || null,
      credential_ref: accessToken.trim() ? "(from PUT /secrets/…)" : "none:",
      source_type: "EXTERNAL_CLONE",
    }),
    [regName, regProvider, regRemoteUrl, regDefaultBranch, accessToken],
  );

  const handleClose = () => {
    setAccessToken("");
    onClose();
  };

  const resetBrownfield = () => {
    setSelectedRepositoryId("");
    setActiveRepositoryId(null);
    setRegName("");
    setRegRemoteUrl("");
    setRegDefaultBranch("");
    setAccessToken("");
    setRepoMode("existing");
  };

  const invalidateRepos = () => {
    if (!projectId) return;
    void queryClient.invalidateQueries({ queryKey: queryKeys.repositories.list(projectId) });
    if (trackedRepositoryId) {
      void queryClient.invalidateQueries({
        queryKey: queryKeys.repositories.detail(trackedRepositoryId),
      });
      void queryClient.invalidateQueries({
        queryKey: queryKeys.repositories.materializations(trackedRepositoryId),
      });
    }
  };

  const registerNewRepository = async (idem: string) => {
    if (!projectId || !regName.trim() || !regRemoteUrl.trim()) {
      throw new Error("Name and remote URL are required.");
    }
    const projectKey = project.data?.key;
    if (!projectKey) throw new Error("Project not loaded.");

    let credentialRef = "none:";
    if (accessToken.trim()) {
      const secretName = secretNameForRepo(projectKey, regName.trim());
      const stored = await putSecret(secretName, accessToken.trim(), newIdempotencyKey());
      credentialRef = stored.credential_ref;
      setAccessToken("");
    }

    const repo = await registerRepository(
      projectId,
      {
        name: regName.trim(),
        provider: regProvider,
        remote_url: regRemoteUrl.trim(),
        default_branch: regDefaultBranch.trim() || null,
        credential_ref: credentialRef,
      },
      idem,
    );
    setActiveRepositoryId(repo.id);
    setSelectedRepositoryId(repo.id);
    await queryClient.invalidateQueries({ queryKey: queryKeys.repositories.list(projectId) });
  };

  const submit = async () => {
    if (!projectId || !objective.trim()) return;
    if (isBrownfield) {
      if (!trackedRepositoryId || !repositoryReady) {
        setError("Choose a repository and wait until materialization is READY.");
        return;
      }
    }
    setBusy(true);
    setError(null);
    try {
      const cycle = await createDeliveryCycleCommand(
        projectId,
        meta.type,
        objective.trim(),
        isBrownfield ? trackedRepositoryId : null,
        newIdempotencyKey(),
      );
      await queryClient.invalidateQueries({ queryKey: ["delivery-cycles", projectId] });
      setObjective("");
      resetBrownfield();
      handleClose();
      router.push(`/projects/${projectId}/cycles/${cycle.id}/studio`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Create cycle failed");
    } finally {
      setBusy(false);
    }
  };

  const canCreate =
    Boolean(objective.trim()) &&
    (!isBrownfield || (Boolean(trackedRepositoryId) && repositoryReady));

  return (
    <ModalDialog
      open={open && Boolean(projectId)}
      onClose={handleClose}
      label="New delivery cycle"
      title="Intent-specific intake"
      wide
      footer={
        <>
          <Button onClick={handleClose}>Cancel</Button>
          <Button variant="primary" disabled={!canCreate || busy} onClick={submit}>
            Create delivery cycle
          </Button>
        </>
      }
    >
      <div className="ol-appr">
        <div className="ol-seg ol-seg-wide" role="radiogroup" aria-label="Journey">
          {(Object.keys(JOURNEYS) as JourneyKey[]).map((id) => (
            <button
              key={id}
              type="button"
              role="radio"
              aria-checked={journey === id}
              className={cn("ol-seg-i", journey === id && "is-on")}
              onClick={() => {
                setJourney(id);
                if (id !== "BF") resetBrownfield();
              }}
            >
              {JOURNEYS[id].label}
            </button>
          ))}
        </div>

        {isBrownfield && projectId && (
          <div className="ol-appr">
            <div className="ol-seg" role="radiogroup" aria-label="Repository source">
              <button
                type="button"
                role="radio"
                aria-checked={repoMode === "existing"}
                className={cn("ol-seg-i", repoMode === "existing" && "is-on")}
                onClick={() => setRepoMode("existing")}
              >
                Existing repository
              </button>
              <button
                type="button"
                role="radio"
                aria-checked={repoMode === "register"}
                className={cn("ol-seg-i", repoMode === "register" && "is-on")}
                onClick={() => setRepoMode("register")}
              >
                Register new
              </button>
            </div>

            {repoMode === "existing" && (
              <label className="ol-field">
                <span className="ol-label">Project repository</span>
                <select
                  value={selectedRepositoryId}
                  onChange={(e) => {
                    setSelectedRepositoryId(e.target.value);
                    setActiveRepositoryId(null);
                  }}
                >
                  <option value="">Select…</option>
                  {(repositories.data ?? []).map((r) => (
                    <option key={r.id} value={r.id}>
                      {r.name} · {r.provider} · {r.status}
                    </option>
                  ))}
                </select>
              </label>
            )}

            {repoMode === "register" && (
              <>
                <label className="ol-field">
                  <span className="ol-label">Name</span>
                  <input value={regName} onChange={(e) => setRegName(e.target.value)} />
                </label>
                <label className="ol-field">
                  <span className="ol-label">Provider</span>
                  <select
                    value={regProvider}
                    onChange={(e) => setRegProvider(e.target.value as RepositoryProvider)}
                  >
                    {PROVIDERS.map((p) => (
                      <option key={p} value={p}>
                        {p}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="ol-field">
                  <span className="ol-label">Remote URL</span>
                  <input
                    value={regRemoteUrl}
                    onChange={(e) => setRegRemoteUrl(e.target.value)}
                    placeholder="https://github.com/org/repo.git"
                  />
                </label>
                <label className="ol-field">
                  <span className="ol-label">Default branch (optional)</span>
                  <input
                    value={regDefaultBranch}
                    onChange={(e) => setRegDefaultBranch(e.target.value)}
                    placeholder="main"
                  />
                </label>
                <label className="ol-field">
                  <span className="ol-label">Access token (optional, sent once)</span>
                  <input
                    type="password"
                    autoComplete="off"
                    value={accessToken}
                    onChange={(e) => setAccessToken(e.target.value)}
                  />
                </label>
                {accessToken.trim() && project.data?.key && regName.trim() && (
                  <code className="ol-cmd-api">
                    {previewPutSecret(secretNameForRepo(project.data.key, regName.trim()))}
                  </code>
                )}
                <StudioMutationAction
                  label="Register repository"
                  path={`/projects/${projectId}/repositories`}
                  body={registerPreviewBody}
                  disabled={!regName.trim() || !regRemoteUrl.trim() || !project.data?.key}
                  onRun={registerNewRepository}
                />
              </>
            )}

            {trackedRepositoryId && (
              <RepositoryMaterializationPanel
                repositoryId={trackedRepositoryId}
                onRetryDone={invalidateRepos}
              />
            )}
          </div>
        )}

        <label className="ol-field">
          <span className="ol-label">Objective</span>
          <textarea
            rows={4}
            value={objective}
            onChange={(ev) => setObjective(ev.target.value)}
            placeholder="What this delivery cycle must achieve — stored as cycle objective."
          />
        </label>
        {projectId && (
          <code className="ol-cmd-api">
            {previewCreateCycle(
              projectId,
              meta.type,
              objective,
              isBrownfield ? trackedRepositoryId : null,
            )}
          </code>
        )}
        {error && (
          <div className="ol-sent" role="alert">
            {error}
          </div>
        )}
      </div>
    </ModalDialog>
  );
}
