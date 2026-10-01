import type { z } from "zod";
import type * as E from "./entities";

export type Project = z.infer<typeof E.Project>;
export type DeliveryCycle = z.infer<typeof E.DeliveryCycle>;
export type TransitionPreview = z.infer<typeof E.TransitionPreview>;
export type Task = z.infer<typeof E.Task>;
export type TaskDependency = z.infer<typeof E.TaskDependency>;
export type TaskContract = z.infer<typeof E.TaskContract>;
export type Execution = z.infer<typeof E.Execution>;
export type ExecutionSnapshot = z.infer<typeof E.ExecutionSnapshot>;
export type DomainEvent = z.infer<typeof E.DomainEvent>;
export type Approval = z.infer<typeof E.Approval>;
export type IntegrationCandidate = z.infer<typeof E.IntegrationCandidate>;
export type Gate = z.infer<typeof E.Gate>;
export type Finding = z.infer<typeof E.Finding>;
export type ReleaseEligibilityEvaluation = z.infer<typeof E.ReleaseEligibilityEvaluation>;
export type Release = z.infer<typeof E.Release>;
export type ActorMe = z.infer<typeof E.ActorMe>;

export type CodeEntity = z.infer<typeof E.CodeEntity>;
export type CodeRelation = z.infer<typeof E.CodeRelation>;
export type CodeIndexVersion = z.infer<typeof E.CodeIndexVersion>;
export type IndexPointer = z.infer<typeof E.IndexPointer>;
export type SpecCodeLink = z.infer<typeof E.SpecCodeLink>;
export type LineageGraph = z.infer<typeof E.LineageGraph>;
export type LineageNode = z.infer<typeof E.LineageNode>;
export type LineageEdge = z.infer<typeof E.LineageEdge>;
export type ActionRequest = z.infer<typeof E.ActionRequest>;
export type ActionResult = z.infer<typeof E.ActionResult>;
export type Worktree = z.infer<typeof E.Worktree>;
export type ExecutionWorkspace = z.infer<typeof E.ExecutionWorkspace>;
export type CandidateCommit = z.infer<typeof E.CandidateCommit>;
export type Repository = z.infer<typeof E.Repository>;
export type RepositoryWorkspace = z.infer<typeof E.RepositoryWorkspace>;
export type RepositoryRevision = z.infer<typeof E.RepositoryRevision>;
export type RepositoryMaterialization = z.infer<typeof E.RepositoryMaterialization>;
export type CommitLedgerEntry = z.infer<typeof E.CommitLedgerEntry>;
export type ExecutionLease = z.infer<typeof E.ExecutionLease>;
export type ModelCall = z.infer<typeof E.ModelCall>;
export type Artifact = z.infer<typeof E.Artifact>;
export type RuntimeMetadata = z.infer<typeof E.RuntimeMetadata>;
export type IntegrationCandidateCommit = z.infer<typeof E.IntegrationCandidateCommit>;
export type Evidence = z.infer<typeof E.Evidence>;
export type VerificationObligation = z.infer<typeof E.VerificationObligation>;
export type AcceptanceCoverage = z.infer<typeof E.AcceptanceCoverage>;
export type Review = z.infer<typeof E.Review>;
export type ReleaseManifest = z.infer<typeof E.ReleaseManifest>;
export type ControlDecision = z.infer<typeof E.ControlDecision>;
export type Requirement = z.infer<typeof E.Requirement>;
export type UserStory = z.infer<typeof E.UserStory>;
export type KnowledgeItem = z.infer<typeof E.KnowledgeItem>;
export type ObservedBehavior = z.infer<typeof E.ObservedBehavior>;
export type PromotionDecision = z.infer<typeof E.PromotionDecision>;
export type CodeEntityChange = z.infer<typeof E.CodeEntityChange>;

export type ProductSource = z.infer<typeof E.ProductSource>;
export type Capability = z.infer<typeof E.Capability>;
export type Feature = z.infer<typeof E.Feature>;
export type FeatureSpec = z.infer<typeof E.FeatureSpec>;
export type AcceptanceCriterion = z.infer<typeof E.AcceptanceCriterion>;
export type ImplementationSpec = z.infer<typeof E.ImplementationSpec>;
export type Architecture = z.infer<typeof E.Architecture>;
export type TaskPlan = z.infer<typeof E.TaskPlan>;

export type RecoveredSpec = z.infer<typeof E.RecoveredSpec>;
export type BehavioralBaseline = z.infer<typeof E.BehavioralBaseline>;
export type BaselineSet = z.infer<typeof E.BaselineSet>;
export type ReadinessAssessment = z.infer<typeof E.ReadinessAssessment>;
export type RepositoryDiscovery = z.infer<typeof E.RepositoryDiscovery>;

export type ImpactAssessment = z.infer<typeof E.ImpactAssessment>;
export type SpecDelta = z.infer<typeof E.SpecDelta>;

export type Defect = z.infer<typeof E.Defect>;
export type Reproduction = z.infer<typeof E.Reproduction>;
export type TraceCorrelation = z.infer<typeof E.TraceCorrelation>;
export type RootCauseAnalysis = z.infer<typeof E.RootCauseAnalysis>;

export type ChangeRequest = z.infer<typeof E.ChangeRequest>;
export type ConnectorConfig = z.infer<typeof E.ConnectorConfig>;
export type InboundEvent = z.infer<typeof E.InboundEvent>;
export type ConnectorAction = z.infer<typeof E.ConnectorAction>;

export type ProjectSummaryView = z.infer<typeof E.ProjectSummaryView>;
export type CycleOverviewView = z.infer<typeof E.CycleOverviewView>;
export type ControlPlaneView = z.infer<typeof E.ControlPlaneView>;
