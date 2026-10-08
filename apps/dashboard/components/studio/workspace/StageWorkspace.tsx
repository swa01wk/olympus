"use client";

import { ArchitectureStage } from "@/components/studio/workspace/ArchitectureStage";
import { DevelopmentStage } from "@/components/studio/workspace/DevelopmentStage";
import { DiscoveryStage } from "@/components/studio/workspace/DiscoveryStage";
import { IntegrationAssuranceStage } from "@/components/studio/workspace/IntegrationAssuranceStage";
import { PlanningStage } from "@/components/studio/workspace/PlanningStage";
import { ProductModelStage } from "@/components/studio/workspace/ProductModelStage";
import { ReleaseStage } from "@/components/studio/workspace/ReleaseStage";
import { UnsupportedStage } from "@/components/studio/workspace/UnsupportedStage";
import { BugFixStage } from "@/components/studio/workspace/journeys/BugFixStage";
import { BrownfieldBaselineStage } from "@/components/studio/workspace/journeys/BrownfieldBaselineStage";
import { BrownfieldCodeIndexStage } from "@/components/studio/workspace/journeys/BrownfieldCodeIndexStage";
import { BrownfieldReadinessStage } from "@/components/studio/workspace/journeys/BrownfieldReadinessStage";
import { BrownfieldReadyStage } from "@/components/studio/workspace/journeys/BrownfieldReadyStage";
import { BrownfieldReconStage } from "@/components/studio/workspace/journeys/BrownfieldReconStage";
import { BrownfieldRecoveredSpecStage } from "@/components/studio/workspace/journeys/BrownfieldRecoveredSpecStage";
import { BrownfieldRemediationStage } from "@/components/studio/workspace/journeys/BrownfieldRemediationStage";
import { FeatureChangeIntakeStage } from "@/components/studio/workspace/journeys/FeatureChangeIntakeStage";
import { ImpactAnalysisStage } from "@/components/studio/workspace/journeys/ImpactAnalysisStage";
import { RemediationIntakeStage } from "@/components/studio/workspace/journeys/RemediationIntakeStage";
import { SpecDeltaStage } from "@/components/studio/workspace/journeys/SpecDeltaStage";
import { isKnownStudioStage, SHARED_EXECUTION_STAGES } from "@/lib/studio-workspace";
import type { DeliveryCycle, InboxItem } from "@/src/api/types/core";
import type { DeliveryCycleType } from "@/src/control-plane/stage-lanes";

function greenfieldStageView(
  stage: string,
  projectId: string,
  cycleId: string,
  inbox: InboxItem[],
) {
  switch (stage) {
    case "DISCOVERY":
      return <DiscoveryStage projectId={projectId} cycleId={cycleId} />;
    case "PRODUCT_MODEL":
      return <ProductModelStage projectId={projectId} cycleId={cycleId} inbox={inbox} />;
    case "ARCHITECTURE":
      return <ArchitectureStage projectId={projectId} cycleId={cycleId} />;
    case "PLANNING":
      return <PlanningStage projectId={projectId} cycleId={cycleId} />;
    case "DEVELOPMENT":
      return <DevelopmentStage projectId={projectId} cycleId={cycleId} />;
    case "INTEGRATION":
    case "ASSURANCE":
      return (
        <IntegrationAssuranceStage projectId={projectId} cycleId={cycleId} stage={stage} />
      );
    case "RELEASE":
    case "COMPLETE":
      return <ReleaseStage projectId={projectId} cycleId={cycleId} />;
    default:
      return null;
  }
}

function sharedExecutionStage(
  cycleType: DeliveryCycleType,
  stage: string,
  projectId: string,
  cycleId: string,
  inbox: InboxItem[],
) {
  if (cycleType === "GREENFIELD_BUILD") {
    return greenfieldStageView(stage, projectId, cycleId, inbox);
  }
  if (!SHARED_EXECUTION_STAGES.has(stage)) return null;
  return greenfieldStageView(stage, projectId, cycleId, inbox);
}

export function StageWorkspace({
  projectId,
  cycle,
  stage,
  inbox,
}: {
  projectId: string;
  cycle: DeliveryCycle;
  stage: string;
  inbox: InboxItem[];
}) {
  const cycleId = cycle.id;
  const cycleType = cycle.type as DeliveryCycleType;

  if (!isKnownStudioStage(cycleType, stage)) {
    return <UnsupportedStage cycleType={cycleType} stage={stage} />;
  }

  const shared = sharedExecutionStage(cycleType, stage, projectId, cycleId, inbox);
  if (shared) return shared;

  switch (cycleType) {
    case "FEATURE_CHANGE":
      switch (stage) {
        case "INTAKE":
          return <FeatureChangeIntakeStage projectId={projectId} cycleId={cycleId} />;
        case "SPEC_DELTA":
          return <SpecDeltaStage cycleId={cycleId} />;
        case "IMPACT_ANALYSIS":
          return <ImpactAnalysisStage cycleId={cycleId} />;
        default:
          break;
      }
      break;
    case "BUG_FIX":
      if (
        stage === "TRIAGE" ||
        stage === "REPRODUCTION" ||
        stage === "EXPECTED_BEHAVIOR" ||
        stage === "ROOT_CAUSE" ||
        stage === "REGRESSION"
      ) {
        return (
          <BugFixStage projectId={projectId} cycleId={cycleId} stage={stage} />
        );
      }
      break;
    case "BROWNFIELD_ONBOARDING":
      switch (stage) {
        case "RECON":
          return (
            <BrownfieldReconStage
              projectId={projectId}
              cycleId={cycleId}
              repositoryId={cycle.repository_id}
            />
          );
        case "CODE_INDEX":
          return <BrownfieldCodeIndexStage projectId={projectId} cycleId={cycleId} />;
        case "RECOVERED_SPEC":
          return <BrownfieldRecoveredSpecStage cycleId={cycleId} />;
        case "BASELINE":
          return <BrownfieldBaselineStage projectId={projectId} cycleId={cycleId} />;
        case "READINESS":
          return <BrownfieldReadinessStage cycleId={cycleId} />;
        case "REMEDIATION":
          return <BrownfieldRemediationStage projectId={projectId} cycleId={cycleId} />;
        case "READY":
          return <BrownfieldReadyStage projectId={projectId} />;
        default:
          break;
      }
      break;
    case "REMEDIATION":
      if (stage === "INTAKE") {
        return <RemediationIntakeStage cycleId={cycleId} />;
      }
      break;
    default:
      break;
  }

  return <UnsupportedStage cycleType={cycleType} stage={stage} />;
}
