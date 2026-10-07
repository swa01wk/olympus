// Olympus component types — documentation, not type-checked.
// Fixture-driven: `journey` objects come from window.Olympus.fixtures.JOURNEYS.

type LaneId = 'intent' | 'work' | 'exec' | 'code' | 'evidence' | 'outcome';
type ScreenId = 'S01' | 'S02' | 'S03' | 'S04' | 'S05' | 'S06' | 'S07' | 'S08' | 'S09' | 'S10' | 'INT' | 'AUD';
type Lens = 'lifecycle' | 'trace' | 'impact' | 'blockers';
type Prov = 'FACT' | 'INFERENCE' | 'UNCERTAINTY' | 'ASSUMPTION' | 'DECISION';
/** One of the keys of Olympus.model.STATUS, e.g. 'running' | 'missing' | 'approval-pending' | 'future'. */
type Status = string;

interface GNode { id: string; lane: LaneId; kind: string; ref: string; title: string; at: number; st: [number, Status][]; sub?: string; prov?: Prov; conf?: number; origin?: string; sha?: string; stack?: string[]; impact?: 'direct' | 'inferred' | 'scope' }
interface GEdge { from: string; to: string; rel: string; kind?: 'auth' | 'inferred'; conf?: number; note?: string }
interface Journey { id: 'GF' | 'BF' | 'FC' | 'BG'; cycle: string; name: string; objective: string; direction: string; outcome: string; stages: { k: string; lane: LaneId; out: string }[]; live: number; nodes: GNode[]; edges: GEdge[] }
interface Why { summary: string; checks?: [string, boolean | null, string?][]; blocking?: string[]; policy?: string; inputs?: string; next?: string }
interface Cmd { label: string; cmd: string; enabled?: boolean; reason?: string; dialog?: 'approval' | 'checkpoint' | 'intake' }

export interface ButtonProps { variant?: 'primary' | 'quiet' | 'ghost'; size?: 'sm'; disabled?: boolean; title?: string; onClick?: () => void; children?: any }
export interface StatusBadgeProps { status: Status; label?: string; size?: 'sm' }
export interface ProvenanceBadgeProps { kind: Prov; conf?: number; source?: string }
export interface AppShellProps { screen: ScreenId; journey: Journey; stage?: number; onNav?: (s: ScreenId) => void; onCycle?: (cycleId: string) => void; onAsk?: () => void; onNew?: () => void; stream?: 'live' | 'disconnected'; overlay?: any; children?: any }
export interface LifecycleRibbonProps { journey: Journey; stage: number; onStage?: (i: number) => void; compact?: boolean }
export interface JourneySpineProps { journey: Journey; stage: number; width: number; height?: number; centers?: number[]; showLanes?: boolean; onStage?: (i: number) => void }
export interface LaneStripProps { journey: Journey; stage: number; current?: LaneId; onLane?: (l: LaneId) => void; lens?: string }
export interface AttentionStripProps { journey: Journey; stage: number; onSelect?: (id: string) => void; onWhy?: (id: string) => void; onAction?: (id: string) => void }
export interface ObjectNodeProps { node: GNode; status: Status; selected?: boolean; dim?: boolean; impact?: 'direct' | 'inferred' | 'scope'; onClick?: () => void; innerRef?: any }
export interface ControlPlaneGraphProps { journey: Journey; stage: number; selected?: string; onSelect?: (id: string) => void; lens?: Lens; onLens?: (l: Lens) => void; view?: 'graph' | 'list'; onView?: (v: 'graph' | 'list') => void; onOpenLane?: (l: LaneId) => void; onStage?: (i: number) => void; focusEdge?: string | null; hideToolbar?: boolean }
export interface ObjectInspectorProps { journey: Journey; stage: number; id?: string; onSelect?: (id: string) => void; onOpen?: (s: ScreenId, id: string) => void; onCommand?: (c: Cmd, id: string) => void; lens?: Lens; onHoverRel?: (edgeKey: string | null) => void }
export interface WhyPanelProps { why: Why; onRef?: (id: string) => void; evaluated?: string }
export interface EvidenceMatrixProps { groups: { name: string; rows: [string, string, string, Status, string?][] }[]; target: string; onRef?: (id: string) => void }
export interface EligibilityChecklistProps { items: [string, Status, string][]; title?: string }
export interface TaskContractCardProps { contract: { version: string; objective: string; workType: string; inputs: string[]; base: string; allowed: string[]; constraints: string[]; prohibited: string[]; outputs: string[]; verification: string[]; escalation: string[] }; taskId: string }
export interface ExecutionTimelineProps { events: [string, string, string, 'allowed' | 'denied' | 'platform' | 'failed' | 'passed'][] }
export interface TaskDagProps { journey: Journey; stage: number; selected?: string; onSelect?: (id: string) => void }
export interface VersionDiffProps { left: string[]; right: string[]; leftLabel: string; rightLabel: string }
export interface ShaScopeBannerProps { scopes: { k: string; label: string; ref: string; sha: string; note: string }[]; active: string; onChange?: (k: string) => void; message?: string }
export interface ApprovalDialogProps { open?: boolean; onClose?: () => void; inline?: boolean; subject: { type: string; id: string; scope: string; version: string; sha: string; reason: string; impact: string; risk: string; records: string[]; cmd: string } }
export interface CheckpointDialogProps { open?: boolean; onClose?: () => void; inline?: boolean; c: { id: string; q: string; unknown: string; checked: string[]; answer: string; waiting: string } }
export interface IntakeFormProps { open?: boolean; onClose?: () => void; inline?: boolean; initial?: 'GF' | 'BF' | 'FC' | 'BG' }
/** The whole fixture-driven prototype; every screen card renders this. */
export interface OlympusAppProps { screen?: ScreenId; cycle?: 'DC-001' | 'DC-002' | 'DC-003' | 'DC-004'; stage?: number; lens?: Lens; select?: string; view?: 'graph' | 'list'; dialog?: 'approval' | 'checkpoint' | 'intake'; drawer?: 'ask' | 'why'; stream?: 'live' | 'disconnected' }
