"use client";

import { ClarificationDraftCard } from "@/components/studio/chat/ClarificationDraftCard";
import { ProposalCard } from "@/components/studio/chat/ProposalCard";
import { splitExplainText } from "@/lib/record-stage-links";
import { turnText } from "@/lib/chat-transcript";
import type { ProposalRouteContext } from "@/src/api/proposal-routes";
import type { Clarification } from "@/src/api/types/product-model";
import type { OrchestratorTurn } from "@/src/api/types/orchestrator";
import Link from "next/link";

export function ChatTurnView({
  turn,
  ctx,
  studioBasePath,
  clarifications,
  dismissedProposalKey,
  onDismissProposal,
  onProposalRan,
  onClarificationAnswered,
  onSelectStage,
}: {
  turn: OrchestratorTurn;
  ctx: ProposalRouteContext;
  studioBasePath: string;
  clarifications: Clarification[];
  dismissedProposalKey?: string;
  onDismissProposal: (key: string) => void;
  onProposalRan?: () => void;
  onClarificationAnswered?: () => void;
  onSelectStage: (stage: string) => void;
}) {
  const intent = turn.intent ?? "EXPLAIN";
  const text = turnText(turn);
  const proposalKey = turn.proposal
    ? `${turn.proposal.command}:${turn.proposal.target_ref}`
    : "";

  if (intent === "OUT_OF_SCOPE") {
    return <p className="ol-body ol-muted">{text}</p>;
  }

  if (intent === "NAVIGATE") {
    return <p className="ol-body">{text}</p>;
  }

  if (intent === "PROPOSE_COMMAND" && turn.proposal && dismissedProposalKey !== proposalKey) {
    return (
      <div className="ol-chat-turn-block">
        {text && <p className="ol-body">{text}</p>}
        <ProposalCard
          proposal={turn.proposal}
          ctx={ctx}
          studioHref={studioBasePath}
          onDismiss={() => onDismissProposal(proposalKey)}
          onRan={onProposalRan}
        />
      </div>
    );
  }

  if (intent === "ANSWER_CLARIFICATION" && turn.clarification_answer_draft) {
    return (
      <div className="ol-chat-turn-block">
        {text && <p className="ol-body">{text}</p>}
        <ClarificationDraftCard
          draft={turn.clarification_answer_draft}
          clarifications={clarifications}
          onAnswered={onClarificationAnswered}
        />
      </div>
    );
  }

  return (
    <div className="ol-chat-explain ol-body">
      {splitExplainText(text).map((seg, i) =>
        seg.kind === "text" ? (
          <span key={i}>{seg.value}</span>
        ) : seg.stage ? (
          <Link
            key={i}
            href={`${studioBasePath}?stage=${encodeURIComponent(seg.stage)}`}
            className="ol-chat-record-link"
            onClick={(e) => {
              e.preventDefault();
              onSelectStage(seg.stage!);
            }}
          >
            {seg.value}
          </Link>
        ) : (
          <span key={i} className="ol-id">
            {seg.value}
          </span>
        ),
      )}
    </div>
  );
}
