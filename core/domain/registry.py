"""Import all ORM models so Alembic metadata is complete."""

from core.assurance.models import (  # noqa: F401
    AcceptanceCoverage,
    Evidence,
    Finding,
    Gate,
    VerificationObligation,
    VerificationPlanRow,
    WardenReviewRecord,
)
from core.domain.actions.models import ActionRequest, ActionResult  # noqa: F401
from core.domain.actors.models import Actor, ApiToken  # noqa: F401
from core.domain.approvals.models import Approval  # noqa: F401
from core.domain.artifacts.models import Artifact  # noqa: F401
from core.domain.audit.models import AuditEvent  # noqa: F401
from core.domain.candidate_commits.models import CandidateCommit  # noqa: F401
from core.domain.connectors.models import ConnectorActionRecord, ConnectorResultRecord  # noqa: F401
from core.domain.delivery_cycles.models import DeliveryCycle  # noqa: F401
from core.domain.events.models import DomainEvent  # noqa: F401
from core.domain.execution_tokens.models import ExecutionToken  # noqa: F401
from core.domain.execution_workspaces.models import ExecutionWorkspace  # noqa: F401
from core.domain.executions.models import (  # noqa: F401
    Checkpoint,
    Clarification,
    Execution,
    ExecutionEvent,
    ExecutionLease,
    ExecutionSnapshot,
)
from core.domain.integrations.models import (  # noqa: F401
    ConnectorConfig,
    DeploymentRecord,
    ExternalLink,
    ReconciliationItem,
    RepositoryEvent,
    StoredSecret,
)
from core.domain.model_calls.models import ModelCall  # noqa: F401
from core.domain.policy.models import CommandLog, PolicyVersion  # noqa: F401
from core.domain.projects.models import Project, ProjectSequence  # noqa: F401
from core.domain.repositories.materializations import RepositoryMaterialization  # noqa: F401
from core.domain.repositories.models import (  # noqa: F401
    Repository,
    RepositoryRevision,
    RepositoryWorkspace,
)
from core.domain.task_contracts.models import TaskContract  # noqa: F401
from core.domain.tasks.models import Task, TaskDependency  # noqa: F401
from core.integration.models import (  # noqa: F401
    IntegrationCandidate,
    IntegrationCandidateCommit,
)
from core.integrations.inbound.models import InboundEvent, IntegrationSource  # noqa: F401
from core.intelligence.baselines.models import (  # noqa: F401
    BaselineSet,
    BaselineSetItem,
    BehavioralBaseline,
    PromotionDecision,
    ReadinessAssessment,
)
from core.intelligence.brownfield.models import (  # noqa: F401
    ObservedBehavior,
    RecoveredSpecEvidence,
    RecoveryProposal,
    RepositoryDiscovery,
)
from core.intelligence.code_index.models import (  # noqa: F401
    CodeEntity,
    CodeIndexVersion,
    CodeRelation,
)
from core.intelligence.impact.models import (  # noqa: F401
    Embedding,
    ImpactAssessment,
    ImpactItem,
    SpecDelta,
    StalenessEvent,
)
from core.orchestrator.models import OrchestratorSession  # noqa: F401
from core.planning.models import (  # noqa: F401
    Architecture,
    ArchitectureContract,
    ImplementationSpec,
    TaskPlanRow,
    TaskSpecRef,
)
from core.product_model.changes.models import ChangeRequest  # noqa: F401
from core.product_model.defects.models import (  # noqa: F401
    Defect,
    ExpectedBehaviorResolution,
    Reproduction,
    RootCauseAnalysis,
    TraceCorrelation,
)
from core.product_model.models import (  # noqa: F401
    AcceptanceCriterion,
    Capability,
    Feature,
    FeatureSpec,
    KnowledgeItem,
    ProductDecomposition,
    ProductSource,
    Requirement,
    ScopeSet,
    ScopeSetItem,
    UserStory,
)
from core.release.models import (  # noqa: F401
    DeliveryOutcome,
    Release,
    ReleaseEligibilityEvaluation,
    ReleaseManifest,
)
from core.traceability.models import (  # noqa: F401
    CodeEntityChange,
    RepositoryIndexPointer,
    SpecCodeLink,
)
