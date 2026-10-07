import { Button, StatusBadge, ProvenanceBadge, ShaScopeBanner, IdRef, Sha, Panel, KV, EmptyState } from './primitives';
import { AppShell, TopBar, NavRail, LifecycleRibbon, JourneySpine, LaneStrip, AttentionStrip, CycleHeader } from './shell';
import { ObjectNode, ControlPlaneGraph } from './graph';
import { ObjectInspector, WhyPanel, CommandList } from './inspector';
import { EvidenceMatrix, EligibilityChecklist, TaskContractCard, ExecutionTimeline, AttemptHistory, VersionDiff, TaskDag, ApprovalDialog, CheckpointDialog, IntakeForm, Dialog, Drawer } from './parts';
import { OlympusApp, approvalFor } from './screens';
import { JourneyMatrix, NavigationModel, ExceptionStates } from './pages';
import { JOURNEYS, journeyById } from './data';
import { DETAIL } from './detail';
import * as model from './model';

(window as any).Olympus = {
  Button, StatusBadge, ProvenanceBadge, ShaScopeBanner, IdRef, Sha, Panel, KV, EmptyState,
  AppShell, TopBar, NavRail, LifecycleRibbon, JourneySpine, LaneStrip, AttentionStrip, CycleHeader,
  ObjectNode, ControlPlaneGraph, ObjectInspector, WhyPanel, CommandList,
  EvidenceMatrix, EligibilityChecklist, TaskContractCard, ExecutionTimeline, AttemptHistory, VersionDiff, TaskDag,
  ApprovalDialog, CheckpointDialog, IntakeForm, Dialog, Drawer,
  OlympusApp, JourneyMatrix, NavigationModel, ExceptionStates,
  fixtures: { JOURNEYS, journeyById, DETAIL, approvalFor },
  model,
};
