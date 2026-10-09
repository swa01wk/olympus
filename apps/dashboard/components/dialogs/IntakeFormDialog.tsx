"use client";

import { ModalDialog } from "@/components/dialogs/ModalDialog";
import { Button, Label } from "@/components/primitives";
import { StudioMutationAction } from "@/components/studio/workspace/StudioMutationAction";
import {
  previewCreateCycle,
  previewIntake,
  previewPutSecret,
} from "@/lib/command-preview";
import { cn, newIdempotencyKey } from "@/lib/utils";
import { isApiError } from "@/src/api/client";
import {
  createDeliveryCycleCommand,
  intakeChangeRequest,
  intakeDefect,
  putSecret,
  registerRepository,
  retryMaterialization,
} from "@/src/api/commands";
import { useActorMe, useProject } from "@/src/api/hooks/use-olympus-queries";
import {
  useProjectRepositories,
  useRepository,
  useRepositoryMaterializations,
} from "@/src/api/hooks/use-journey-queries";
import { queryKeys } from "@/src/api/query-keys";
import { useProjectEventStream } from "@/src/api/sse/use-project-event-stream";
import type { DomainEventPayload } from "@/src/api/types/core";
import type { RepositoryProvider } from "@/src/api/types/repository";
import { useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";

const JOURNEYS = {
  GF: { label: "Greenfield Build", type: "GREENFIELD_BUILD", intake: null },
  BF: { label: "Brownfield Onboarding", type: "BROWNFIELD_ONBOARDING", intake: null },
  FC: { label: "Feature Change", type: "FEATURE_CHANGE", intake: "change-requests" },
  BG: { label: "Bug Fix", type: "BUG_FIX", intake: "defects" },
} as const;

type JourneyKey = keyof typeof JOURNEYS;

const PROVIDERS: { value: RepositoryProvider; supported: boolean }[] = [
  { value: "GITHUB", supported: true },
  { value: "GITEA", supported: true },
  { value: "GITLAB", supported: false },
  { value: "BITBUCKET", supported: false },
  { value: "LOCAL", supported: true },
];

const OPERATOR_ROLE_MESSAGE = "You need the OPERATOR role to do this.";

/** Secret names must fit `credential_ref` (`[A-Za-z0-9_./-]`) and the 128-char `secrets.name` column. */
const SECRET_NAME_MAX = 120;

export function secretNameForRepo(projectKey: string, repoName: string): string {
  return `repo-${projectKey}-${repoName}`
    .toLowerCase()
    .replace(/[^a-z0-9_.-]+/g, "-")
    .replace(/-{2,}/g, "-")
    .slice(0, SECRET_NAME_MAX)
    .replace(/^[-.]+|[-.]+$/g, "");
}

function errorMessage(e: unknown, fallback: string): string {
  return isApiError(e) ? e.message : e instanceof Error ? e.message : fallback;
}

function RepositoryMaterializationPanel({
  repositoryId,
  repo,
  canOperate,
  onRetryDone,
}: {
  repositoryId: string;
  repo: ReturnType<typeof useRepository>;
  canOperate: boolean;
  onRetryDone: () => void;
}) {
  const materializations = useRepositoryMaterializations(
    repo.data?.status === "ERROR" ? repositoryId : undefined,
  );
  const lastAttempt = materializations.data?.[materializations.data.length - 1];

  if (repo.isLoading && !repo.data) {
    return <p className="ol-body-sm ol-muted">Loading repository status…</p>;
  }

  const r = repo.data;
  if (!r) {
    return repo.isError ? (
      <p className="ol-body-sm ol-chat-err" role="alert">
        Could not load repository: {errorMessage(repo.error, "request failed")}
      </p>
    ) : null;
  }

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
      {r.status === "ERROR" && (
        <>
          {lastAttempt?.error_class && (
            <div>
              <Label>Last error class</Label>
              <div className="ol-body-sm">{lastAttempt.error_class}</div>
            </div>
          )}
          {lastAttempt?.error_detail && (
            <div>
              <Label>Last error detail</Label>
              <div className="ol-body-sm">{lastAttempt.error_detail}</div>
            </div>
          )}
          <StudioMutationAction
            label="Retry materialization"
            path={`/repositories/${repositoryId}/commands/retry_materialization`}
            disabled={!canOperate}
            onRun={async (idem) => {
              await retryMaterialization(repositoryId, idem);
              onRetryDone();
            }}
          />
        </>
      )}
      {r.status !== "READY" && r.status !== "ERROR" && (
        <p className="ol-body-sm ol-muted">
          Polling GET /repositories/{repositoryId} every 3 s and refreshing on repository.* events…
        </p>
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
  const actor = useActorMe();
  const project = useProject(projectId ?? undefined);
  const repositories = useProjectRepositories(projectId ?? undefined, { enabled: open });
  const canOperate = (actor.data?.roles ?? []).includes("OPERATOR");

  const [journey, setJourney] = useState<JourneyKey>("FC");
  const [objective, setObjective] = useState("");
  const [title, setTitle] = useState("");
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
  const [credentialRef, setCredentialRef] = useState<string | null>(null);

  const meta = JOURNEYS[journey];
  const isBrownfield = meta.type === "BROWNFIELD_ONBOARDING";
  const intakeKind = meta.intake;

  const existingRepositories = repositories.data ?? [];
  const canRegisterNew = repositories.isSuccess && existingRepositories.length === 0;
  const mode = canRegisterNew ? repoMode : "existing";

  const trackedRepositoryId = activeRepositoryId || selectedRepositoryId || null;
  const trackedRepo = useRepository(isBrownfield ? trackedRepositoryId ?? undefined : undefined, {
    enabled: open,
  });
  const trackedStatus = trackedRepo.data?.status;
  const repositoryReady = trackedStatus === "READY";
  const tracking =
    open &&
    isBrownfield &&
    Boolean(trackedRepositoryId) &&
    trackedStatus !== "READY" &&
    trackedStatus !== "ERROR";

  const projectKey = project.data?.key;
  const hasToken = Boolean(accessToken.trim());
  const pendingSecretName =
    projectKey && regName.trim() ? secretNameForRepo(projectKey, regName.trim()) : null;
  const previewCredentialRef =
    hasToken && pendingSecretName ? `secret:${pendingSecretName}` : (credentialRef ?? "none:");

  const registerPreviewBody = useMemo(
    () => ({
      name: regName.trim(),
      provider: regProvider,
      remote_url: regRemoteUrl.trim(),
      default_branch: regDefaultBranch.trim() || null,
      credential_ref: previewCredentialRef,
      source_type: "EXTERNAL_CLONE",
    }),
    [regName, regProvider, regRemoteUrl, regDefaultBranch, previewCredentialRef],
  );

  const invalidateRepos = () => {
    if (!projectId) return;
    void queryClient.invalidateQueries(
      { queryKey: queryKeys.repositories.list(projectId) },
      { cancelRefetch: false },
    );
    if (trackedRepositoryId) {
      void queryClient.invalidateQueries(
        { queryKey: queryKeys.repositories.detail(trackedRepositoryId) },
        { cancelRefetch: false },
      );
      void queryClient.invalidateQueries(
        { queryKey: queryKeys.repositories.materializations(trackedRepositoryId) },
        { cancelRefetch: false },
      );
    }
  };

  useProjectEventStream(projectId ?? undefined, {
    enabled: tracking,
    onEvent: (event: DomainEventPayload) => {
      if (event.event_type.startsWith("repository.")) invalidateRepos();
    },
  });

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
    setCredentialRef(null);
    setRepoMode("existing");
  };

  const registerNewRepository = async (idem: string) => {
    if (!projectId || !regName.trim() || !regRemoteUrl.trim()) {
      throw new Error("Name and remote URL are required.");
    }
    if (!projectKey) throw new Error("Project not loaded.");

    const latest = await repositories.refetch({ throwOnError: true });
    if ((latest.data ?? []).length > 0) {
      throw new Error("This project already has a repository. Pick it instead.");
    }

    let ref = credentialRef ?? "none:";
    if (accessToken.trim()) {
      const stored = await putSecret(
        secretNameForRepo(projectKey, regName.trim()),
        accessToken.trim(),
        newIdempotencyKey(),
      );
      ref = stored.credential_ref;
      setCredentialRef(ref);
      setAccessToken("");
    }

    const repo = await registerRepository(
      projectId,
      {
        name: regName.trim(),
        provider: regProvider,
        remote_url: regRemoteUrl.trim(),
        default_branch: regDefaultBranch.trim() || null,
        credential_ref: ref,
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
      let cycleId: string;
      if (intakeKind) {
        const body = { title: title.trim(), description: objective.trim() };
        const res =
          intakeKind === "change-requests"
            ? await intakeChangeRequest(projectId, body)
            : await intakeDefect(projectId, body);
        const created = res.result?.delivery_cycle_id ?? res.result?.cycle_id;
        if (res.status === "REJECTED" || !created) {
          throw new Error(`Intake ${res.status}${res.reason ? `: ${res.reason}` : ""}`);
        }
        cycleId = created;
      } else {
        const cycle = await createDeliveryCycleCommand(
          projectId,
          meta.type,
          objective.trim(),
          isBrownfield ? trackedRepositoryId : null,
          newIdempotencyKey(),
        );
        cycleId = cycle.id;
      }
      await queryClient.invalidateQueries({ queryKey: ["delivery-cycles", projectId] });
      setObjective("");
      setTitle("");
      resetBrownfield();
      handleClose();
      router.push(`/projects/${projectId}/cycles/${cycleId}/studio`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Create cycle failed");
    } finally {
      setBusy(false);
    }
  };

  const canCreate =
    canOperate &&
    Boolean(objective.trim()) &&
    (!intakeKind || Boolean(title.trim())) &&
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
        {!actor.isLoading && !canOperate && (
          <p className="ol-body-sm ol-muted" role="status">
            {OPERATOR_ROLE_MESSAGE}
          </p>
        )}
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
            {canRegisterNew && (
              <div className="ol-seg" role="radiogroup" aria-label="Repository source">
                <button
                  type="button"
                  role="radio"
                  aria-checked={mode === "existing"}
                  className={cn("ol-seg-i", mode === "existing" && "is-on")}
                  onClick={() => setRepoMode("existing")}
                >
                  Existing repository
                </button>
                <button
                  type="button"
                  role="radio"
                  aria-checked={mode === "register"}
                  className={cn("ol-seg-i", mode === "register" && "is-on")}
                  onClick={() => setRepoMode("register")}
                >
                  Register new
                </button>
              </div>
            )}

            {repositories.isLoading && (
              <p className="ol-body-sm ol-muted">Loading project repositories…</p>
            )}
            {repositories.isError && (
              <p className="ol-body-sm ol-chat-err" role="alert">
                Could not load repositories: {errorMessage(repositories.error, "request failed")}
              </p>
            )}

            {mode === "existing" && repositories.isSuccess && (
              <>
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
                    {existingRepositories.map((r) => (
                      <option key={r.id} value={r.id}>
                        {r.name} · {r.provider} · {r.status}
                      </option>
                    ))}
                  </select>
                </label>
                {existingRepositories.length > 0 && (
                  <p className="ol-body-sm ol-muted">A project has one repository.</p>
                )}
              </>
            )}

            {mode === "register" && (
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
                      <option key={p.value} value={p.value} disabled={!p.supported}>
                        {p.supported ? p.value : `${p.value} (not supported yet)`}
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
                {hasToken && pendingSecretName && (
                  <code className="ol-cmd-api">{previewPutSecret(pendingSecretName)}</code>
                )}
                <code className="ol-cmd-api">credential_ref={previewCredentialRef}</code>
                <StudioMutationAction
                  label="Register repository"
                  path={`/projects/${projectId}/repositories`}
                  body={registerPreviewBody}
                  disabled={
                    !canOperate || !regName.trim() || !regRemoteUrl.trim() || !projectKey
                  }
                  onRun={registerNewRepository}
                />
              </>
            )}

            {trackedRepositoryId && (
              <RepositoryMaterializationPanel
                repositoryId={trackedRepositoryId}
                repo={trackedRepo}
                canOperate={canOperate}
                onRetryDone={invalidateRepos}
              />
            )}
          </div>
        )}

        {intakeKind && (
          <label className="ol-field">
            <span className="ol-label">
              {intakeKind === "defects" ? "Defect title" : "Change request title"}
            </span>
            <input value={title} onChange={(ev) => setTitle(ev.target.value)} />
          </label>
        )}
        <label className="ol-field">
          <span className="ol-label">{intakeKind ? "Description" : "Objective"}</span>
          <textarea
            rows={4}
            value={objective}
            onChange={(ev) => setObjective(ev.target.value)}
            placeholder={
              intakeKind
                ? "What should change, or what is broken and what should happen instead."
                : "What this delivery cycle must achieve — stored as cycle objective."
            }
          />
        </label>
        {projectId && (
          <code className="ol-cmd-api">
            {intakeKind
              ? previewIntake(projectId, intakeKind, title)
              : previewCreateCycle(
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
