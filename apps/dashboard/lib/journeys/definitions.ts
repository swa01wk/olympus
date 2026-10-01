/** Display-only journey metadata. Guard logic remains on the server. */

export type JourneyStateDef = {
  state: string;
  label: string;
  forwardCommand?: string;
  capabilities: string[];
};

const greenfield: JourneyStateDef[] = [
  { state: "DISCOVERY", label: "Discovery", forwardCommand: "start_product_modeling", capabilities: ["kira"] },
  { state: "PRODUCT_MODEL", label: "Product Model", forwardCommand: "start_architecture", capabilities: ["kira"] },
  { state: "ARCHITECTURE", label: "Architecture", forwardCommand: "start_planning", capabilities: ["atlas"] },
  { state: "PLANNING", label: "Planning", forwardCommand: "start_development", capabilities: ["kira"] },
  { state: "DEVELOPMENT", label: "Development", forwardCommand: "start_integration", capabilities: ["forge"] },
  { state: "INTEGRATION", label: "Integration", forwardCommand: "start_assurance", capabilities: ["olympus"] },
  { state: "ASSURANCE", label: "Assurance", forwardCommand: "start_release", capabilities: ["warden", "sentinel"] },
  { state: "RELEASE", label: "Release", forwardCommand: "complete", capabilities: ["stratos"] },
  { state: "COMPLETE", label: "Complete", capabilities: [] },
];

const brownfield: JourneyStateDef[] = [
  { state: "RECON", label: "Recon", forwardCommand: "start_code_index", capabilities: ["scout"] },
  { state: "CODE_INDEX", label: "Code Index", forwardCommand: "start_spec_recovery", capabilities: ["scout"] },
  { state: "RECOVERED_SPEC", label: "Recovered Spec", forwardCommand: "start_baseline", capabilities: ["scout"] },
  { state: "BASELINE", label: "Baseline", forwardCommand: "start_readiness", capabilities: ["sentinel"] },
  { state: "READINESS", label: "Readiness", forwardCommand: "declare_ready", capabilities: ["olympus"] },
  { state: "REMEDIATION", label: "Remediation", forwardCommand: "reassess_readiness", capabilities: ["forge"] },
  { state: "READY", label: "Ready", capabilities: [] },
];

const featureChange: JourneyStateDef[] = [
  { state: "INTAKE", label: "Intake", forwardCommand: "start_spec_delta", capabilities: ["kira"] },
  { state: "SPEC_DELTA", label: "Spec Delta", forwardCommand: "start_impact_analysis", capabilities: ["kira"] },
  { state: "IMPACT_ANALYSIS", label: "Impact", forwardCommand: "start_planning", capabilities: ["impact"] },
  ...greenfield.slice(3),
];

const bugFix: JourneyStateDef[] = [
  { state: "TRIAGE", label: "Triage", forwardCommand: "start_reproduction", capabilities: ["kira", "sentinel"] },
  { state: "REPRODUCTION", label: "Reproduction", forwardCommand: "resolve_expected_behavior", capabilities: ["sentinel"] },
  { state: "EXPECTED_BEHAVIOR", label: "Expected Behavior", forwardCommand: "start_root_cause", capabilities: ["kira"] },
  { state: "ROOT_CAUSE", label: "Root Cause", forwardCommand: "start_development", capabilities: ["warden"] },
  { state: "DEVELOPMENT", label: "Development", forwardCommand: "start_integration", capabilities: ["forge"] },
  { state: "INTEGRATION", label: "Integration", forwardCommand: "start_regression", capabilities: ["olympus"] },
  { state: "REGRESSION", label: "Regression", forwardCommand: "start_assurance", capabilities: ["sentinel"] },
  { state: "ASSURANCE", label: "Assurance", forwardCommand: "start_release", capabilities: ["warden", "sentinel"] },
  { state: "RELEASE", label: "Release", forwardCommand: "complete", capabilities: ["stratos"] },
  { state: "COMPLETE", label: "Complete", capabilities: [] },
];

const remediation: JourneyStateDef[] = [
  { state: "INTAKE", label: "Intake", capabilities: ["kira"] },
  ...greenfield.slice(3),
];

export function journeyStates(type: string): JourneyStateDef[] {
  switch (type) {
    case "GREENFIELD_BUILD":
      return greenfield;
    case "BROWNFIELD_ONBOARDING":
      return brownfield;
    case "FEATURE_CHANGE":
      return featureChange;
    case "BUG_FIX":
      return bugFix;
    case "REMEDIATION":
      return remediation;
    default:
      return greenfield;
  }
}
