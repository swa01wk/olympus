/** Control API repository models (`apps/control_api/routers/repositories.py`). */

export type RepositoryProvider =
  | "LOCAL"
  | "GITHUB"
  | "GITEA"
  | "GITLAB"
  | "BITBUCKET";

export type RepositoryStatus =
  | "PROVISIONING"
  | "CLONING"
  | "READY"
  | "SYNCING"
  | "ERROR";

export type RepositoryWorkspace = {
  id: string;
  workspace_type: string;
  storage_backend: string;
  logical_location: string;
  materialized_commit: string | null;
  state: string;
};

export type Repository = {
  id: string;
  project_id: string;
  name: string;
  source_type: string;
  provider: RepositoryProvider;
  remote_url: string | null;
  default_branch: string;
  registered_sha: string | null;
  canonical_commit: string | null;
  released_commit: string | null;
  status: RepositoryStatus;
  status_reason: string | null;
  credential_ref: string;
  credential_status: string;
  workspace: RepositoryWorkspace | null;
};

export type MaterializationAttempt = {
  id: string;
  kind: string;
  attempt: number;
  status: string;
  resulting_sha: string | null;
  observed_default_branch: string | null;
  error_class: string | null;
  error_detail: string | null;
  started_at: string;
  finished_at: string | null;
};

export type RegisterRepositoryInput = {
  name: string;
  provider: RepositoryProvider;
  remote_url: string;
  default_branch?: string | null;
  credential_ref?: string | null;
};
