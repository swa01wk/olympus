export type OrchestratorIntent =
  | "EXPLAIN"
  | "ANSWER_CLARIFICATION"
  | "PROPOSE_COMMAND"
  | "NAVIGATE"
  | "OUT_OF_SCOPE"
  | "REVISION_NOTE_DRAFT";

export type OrchestratorFocus = {
  subject_type: string;
  subject_id: string;
};

export type OrchestratorRevisionNoteDraft = {
  approval_id: string;
  note: string;
};

export type OrchestratorProposal = {
  command: string;
  target_ref: string;
  args: Record<string, unknown>;
  rationale: string;
};

export type OrchestratorClarificationDraft = {
  clarification_id: string;
  answer: string;
};

export type OrchestratorTurn = {
  role: string;
  text: string;
  /** Legacy turns may use `message` instead of `text`. */
  message?: string;
  execution_id?: string;
  intent?: OrchestratorIntent;
  proposal?: OrchestratorProposal | null;
  clarification_answer_draft?: OrchestratorClarificationDraft | null;
  revision_note_draft?: OrchestratorRevisionNoteDraft | null;
  navigate_to?: string | null;
  refs?: string[];
};

export type OrchestratorSession = {
  id: string;
  project_id: string | null;
  delivery_cycle_id: string | null;
  turns: OrchestratorTurn[];
  expires_at: string;
};
