import { afterEach, describe, expect, it, vi } from "vitest";
import {
  acceptTaskPlan,
  answerClarification,
  approveRelease,
  createFeatureSpecVersion,
  createOrchestratorSession,
  createRelease,
  decomposeSource,
  deriveSource,
  executeRelease,
  generateImplementationSpecs,
  generateTaskPlan,
  postOrchestratorTurn,
  proposeArchitecture,
  putSecret,
  registerRepository,
  requestApproval,
  requestArchitectureApproval,
  requestImplementationSpecApproval,
  requestScopeApproval,
  recordPromotionDecision,
  retryMaterialization,
  uploadProductSource,
} from "@/src/api/commands";
import {
  fetchOrchestratorSession,
  fetchReleaseEligibility,
  fetchTaskDag,
  getApproval,
  getNextTransitions,
  getProjectArchitecture,
  getRelease,
  getReleaseManifest,
  getSourceContent,
  listCapabilities,
  listClarifications,
  getCycleSpecDelta,
  listChangeRequests,
  listDecompositions,
  listDefects,
  getFeatureSpec,
  listFeatureSpecs,
  listFeatures,
  listImplementationSpecs,
  listMaterializations,
  listProjectRepositories,
  listSources,
  listTaskPlans,
  getRepository,
} from "@/src/api/resources";

function mockFetchJson(payload: string = "[]") {
  const fetchMock = vi.fn().mockResolvedValue({
    ok: true,
    status: 200,
    text: async () => payload,
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function firstCall(fetchMock: ReturnType<typeof vi.fn>) {
  return fetchMock.mock.calls[0] as [string, RequestInit];
}

describe("C1 studio reads", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("listSources", async () => {
    const fetchMock = mockFetchJson();
    await listSources("proj-1");
    const [url, init] = firstCall(fetchMock);
    expect(url).toContain("/projects/proj-1/sources");
    expect(init.method ?? "GET").toBe("GET");
  });

  it("getSourceContent", async () => {
    const fetchMock = mockFetchJson("{}");
    await getSourceContent("proj-1", "src-2");
    expect(firstCall(fetchMock)[0]).toContain("/projects/proj-1/sources/src-2/content");
  });

  it("listCapabilities", async () => {
    const fetchMock = mockFetchJson();
    await listCapabilities("proj-1");
    expect(firstCall(fetchMock)[0]).toContain("/projects/proj-1/capabilities");
  });

  it("listFeatures", async () => {
    const fetchMock = mockFetchJson();
    await listFeatures("proj-1");
    expect(firstCall(fetchMock)[0]).toContain("/projects/proj-1/features");
  });

  it("getFeatureSpec", async () => {
    const fetchMock = mockFetchJson("{}");
    await getFeatureSpec("spec-1");
    expect(firstCall(fetchMock)[0]).toContain("/specs/spec-1");
  });

  it("listFeatureSpecs", async () => {
    const fetchMock = mockFetchJson();
    await listFeatureSpecs("feat-1");
    expect(firstCall(fetchMock)[0]).toContain("/features/feat-1/specs");
  });

  it("listChangeRequests", async () => {
    const fetchMock = mockFetchJson("[]");
    await listChangeRequests("proj-1");
    expect(firstCall(fetchMock)[0]).toContain("/projects/proj-1/change-requests");
  });

  it("getCycleSpecDelta", async () => {
    const fetchMock = mockFetchJson("{}");
    await getCycleSpecDelta("cyc-1");
    expect(firstCall(fetchMock)[0]).toContain("/delivery-cycles/cyc-1/spec-delta");
  });

  it("listDefects", async () => {
    const fetchMock = mockFetchJson("[]");
    await listDefects("proj-1");
    expect(firstCall(fetchMock)[0]).toContain("/projects/proj-1/defects");
  });

  it("listDecompositions", async () => {
    const fetchMock = mockFetchJson();
    await listDecompositions("cycle-1");
    expect(firstCall(fetchMock)[0]).toContain("/delivery-cycles/cycle-1/decompositions");
  });

  it("listClarifications without filter", async () => {
    const fetchMock = mockFetchJson();
    await listClarifications();
    expect(firstCall(fetchMock)[0]).toContain("/clarifications");
    expect(firstCall(fetchMock)[0]).not.toContain("status=");
  });

  it("listClarifications with status query", async () => {
    const fetchMock = mockFetchJson();
    await listClarifications("OPEN");
    expect(firstCall(fetchMock)[0]).toContain("status=OPEN");
  });

  it("getProjectArchitecture", async () => {
    const fetchMock = mockFetchJson("{}");
    await getProjectArchitecture("proj-1");
    expect(firstCall(fetchMock)[0]).toContain("/projects/proj-1/architecture");
  });

  it("listImplementationSpecs", async () => {
    const fetchMock = mockFetchJson();
    await listImplementationSpecs("fspec-1");
    expect(firstCall(fetchMock)[0]).toContain("/features/fspec-1/implementation-specs");
  });

  it("listTaskPlans", async () => {
    const fetchMock = mockFetchJson();
    await listTaskPlans("cycle-1");
    expect(firstCall(fetchMock)[0]).toContain("/delivery-cycles/cycle-1/task-plans");
  });

  it("getTaskDag via fetchTaskDag view path", async () => {
    const fetchMock = mockFetchJson('{"nodes":[],"edges":[]}');
    await fetchTaskDag("cycle-1");
    expect(firstCall(fetchMock)[0]).toContain("/views/tasks/cycle-1/dag");
  });

  it("getApproval", async () => {
    const fetchMock = mockFetchJson("{}");
    await getApproval("apr-1");
    expect(firstCall(fetchMock)[0]).toContain("/approvals/apr-1");
  });

  it("getNextTransitions", async () => {
    const fetchMock = mockFetchJson();
    await getNextTransitions("cycle-1");
    expect(firstCall(fetchMock)[0]).toContain("/delivery-cycles/cycle-1/next-transitions");
  });

  it("getReleaseEligibility", async () => {
    const fetchMock = mockFetchJson("{}");
    await fetchReleaseEligibility("cycle-1");
    expect(firstCall(fetchMock)[0]).toContain("/delivery-cycles/cycle-1/release-eligibility");
  });

  it("getRelease", async () => {
    const fetchMock = mockFetchJson("{}");
    await getRelease("rel-1");
    expect(firstCall(fetchMock)[0]).toContain("/releases/rel-1");
    expect(firstCall(fetchMock)[0]).not.toContain("/manifest");
  });

  it("getReleaseManifest", async () => {
    const fetchMock = mockFetchJson("{}");
    await getReleaseManifest("rel-1");
    expect(firstCall(fetchMock)[0]).toContain("/releases/rel-1/manifest");
  });

  it("fetchOrchestratorSession", async () => {
    const fetchMock = mockFetchJson('{"id":"s1","turns":[]}');
    await fetchOrchestratorSession("sess-1");
    expect(firstCall(fetchMock)[0]).toContain("/orchestrator/sessions/sess-1");
  });
});

describe("RL1.3 promotion decision client", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("recordPromotionDecision", async () => {
    const fetchMock = mockFetchJson("{}");
    await recordPromotionDecision(
      "cycle-bf",
      {
        subject_type: "FEATURE_SPEC",
        subject_id: "spec-1",
        decision: "DEFER",
        note: "Need more evidence",
      },
      "idem-promo",
    );
    const [url, init] = firstCall(fetchMock);
    expect(url).toContain("/delivery-cycles/cycle-bf/promotion-decisions");
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body as string)).toEqual({
      subject_type: "FEATURE_SPEC",
      subject_id: "spec-1",
      decision: "DEFER",
      note: "Need more evidence",
    });
    expect((init.headers as Record<string, string>)["Idempotency-Key"]).toBe("idem-promo");
  });
});

describe("RL1.2 repository client", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("registerRepository", async () => {
    const fetchMock = mockFetchJson("{}");
    await registerRepository(
      "proj-1",
      {
        name: "app",
        provider: "GITHUB",
        remote_url: "https://github.com/org/app.git",
        default_branch: "main",
      },
      "idem-reg",
    );
    const [url, init] = firstCall(fetchMock);
    expect(url).toContain("/projects/proj-1/repositories");
    expect(init.method).toBe("POST");
    expect((init.headers as Record<string, string>)["Idempotency-Key"]).toBe("idem-reg");
    expect(JSON.parse(init.body as string)).toEqual({
      name: "app",
      provider: "GITHUB",
      remote_url: "https://github.com/org/app.git",
      default_branch: "main",
      credential_ref: "none:",
      source_type: "EXTERNAL_CLONE",
    });
  });

  it("putSecret", async () => {
    const fetchMock = mockFetchJson('{"credential_ref":"secret:repo-1"}');
    await putSecret("repo-PRJ-app", "tok-abc", "idem-sec");
    const [url, init] = firstCall(fetchMock);
    expect(url).toContain("/secrets/repo-PRJ-app");
    expect(init.method).toBe("PUT");
    expect(JSON.parse(init.body as string)).toEqual({ value: "tok-abc" });
    expect((init.headers as Record<string, string>)["Idempotency-Key"]).toBe("idem-sec");
  });

  it("retryMaterialization", async () => {
    const fetchMock = mockFetchJson("{}");
    await retryMaterialization("repo-9", "idem-retry");
    const [url, init] = firstCall(fetchMock);
    expect(url).toContain("/repositories/repo-9/commands/retry_materialization");
    expect(init.method).toBe("POST");
    expect((init.headers as Record<string, string>)["Idempotency-Key"]).toBe("idem-retry");
  });

  it("listProjectRepositories", async () => {
    const fetchMock = mockFetchJson("[]");
    await listProjectRepositories("proj-1");
    expect(firstCall(fetchMock)[0]).toContain("/projects/proj-1/repositories");
  });

  it("getRepository", async () => {
    const fetchMock = mockFetchJson("{}");
    await getRepository("repo-1");
    expect(firstCall(fetchMock)[0]).toContain("/repositories/repo-1");
  });

  it("listMaterializations", async () => {
    const fetchMock = mockFetchJson("[]");
    await listMaterializations("repo-1");
    expect(firstCall(fetchMock)[0]).toContain("/repositories/repo-1/materializations");
  });
});

describe("C1 studio writes", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("uploadProductSource JSON", async () => {
    const fetchMock = mockFetchJson('{"result":{"product_source_id":"ps-1"}}');
    await uploadProductSource("proj-1", "cycle-1", { title: "PRD", text: "body" }, "idem-1");
    const [url, init] = firstCall(fetchMock);
    expect(url).toContain("/projects/proj-1/sources");
    expect(url).toContain("delivery_cycle_id=cycle-1");
    expect(init.method).toBe("POST");
    expect((init.headers as Record<string, string>)["Idempotency-Key"]).toBe("idem-1");
    expect(JSON.parse(init.body as string)).toMatchObject({
      title: "PRD",
      text: "body",
      lineage_key: "default",
      source_type: "PRD",
    });
  });

  it("uploadProductSource multipart file", async () => {
    const fetchMock = mockFetchJson('{"result":{"product_source_id":"ps-2"}}');
    const file = new File(["# PRD"], "prd.md", { type: "text/markdown" });
    await uploadProductSource("proj-1", "cycle-1", { file });
    const [url, init] = firstCall(fetchMock);
    expect(url).toContain("delivery_cycle_id=cycle-1");
    expect(init.method).toBe("POST");
    expect(init.body).toBeInstanceOf(FormData);
    expect((init.headers as Record<string, string>)["Content-Type"]).toBeUndefined();
  });

  it("decomposeSource", async () => {
    const fetchMock = mockFetchJson("{}");
    await decomposeSource("src-1", "cycle-1");
    const [url, init] = firstCall(fetchMock);
    expect(url).toContain("/sources/src-1/decompose");
    expect(JSON.parse(init.body as string)).toEqual({ delivery_cycle_id: "cycle-1" });
  });

  it("deriveSource", async () => {
    const fetchMock = mockFetchJson("{}");
    await deriveSource("src-1", "cycle-1");
    const [url, init] = firstCall(fetchMock);
    expect(url).toContain("/sources/src-1/derive");
    expect(JSON.parse(init.body as string)).toEqual({ delivery_cycle_id: "cycle-1" });
  });

  it("createFeatureSpecVersion", async () => {
    const fetchMock = mockFetchJson("{}");
    const body = {
      behavior: "b",
      summary: "s",
      inputs: [],
      outputs: [],
      rules: [],
    };
    await createFeatureSpecVersion("feat-1", body);
    const [url, init] = firstCall(fetchMock);
    expect(url).toContain("/features/feat-1/specs");
    expect(JSON.parse(init.body as string)).toEqual({ body });
  });

  it("requestScopeApproval", async () => {
    const fetchMock = mockFetchJson("{}");
    await requestScopeApproval("cycle-1", ["s1", "s2"]);
    const [url, init] = firstCall(fetchMock);
    expect(url).toContain("/delivery-cycles/cycle-1/scope/approval-request");
    expect(JSON.parse(init.body as string)).toEqual({ feature_spec_ids: ["s1", "s2"] });
  });

  it("answerClarification", async () => {
    const fetchMock = mockFetchJson("{}");
    await answerClarification("cl-1", "Yes");
    const [url, init] = firstCall(fetchMock);
    expect(url).toContain("/clarifications/cl-1/answer");
    expect(JSON.parse(init.body as string)).toEqual({ answer: "Yes" });
  });

  it("proposeArchitecture", async () => {
    const fetchMock = mockFetchJson("{}");
    await proposeArchitecture("cycle-1");
    const [url, init] = firstCall(fetchMock);
    expect(url).toContain("/delivery-cycles/cycle-1/architecture/propose");
    expect(init.method).toBe("POST");
  });

  it("requestArchitectureApproval", async () => {
    const fetchMock = mockFetchJson("{}");
    await requestArchitectureApproval("arch-1", "cycle-1");
    const [url, init] = firstCall(fetchMock);
    expect(url).toContain("/architectures/arch-1/approval-request");
    expect(JSON.parse(init.body as string)).toEqual({ delivery_cycle_id: "cycle-1" });
  });

  it("generateImplementationSpecs", async () => {
    const fetchMock = mockFetchJson("{}");
    await generateImplementationSpecs("cycle-1");
    expect(firstCall(fetchMock)[0]).toContain(
      "/delivery-cycles/cycle-1/implementation-specs/generate",
    );
  });

  it("requestImplementationSpecApproval", async () => {
    const fetchMock = mockFetchJson("{}");
    await requestImplementationSpecApproval("ispec-1", "cycle-1");
    const [url, init] = firstCall(fetchMock);
    expect(url).toContain("/implementation-specs/ispec-1/approval-request");
    expect(JSON.parse(init.body as string)).toEqual({ delivery_cycle_id: "cycle-1" });
  });

  it("generateTaskPlan", async () => {
    const fetchMock = mockFetchJson("{}");
    await generateTaskPlan("cycle-1");
    expect(firstCall(fetchMock)[0]).toContain("/delivery-cycles/cycle-1/task-plan/generate");
  });

  it("acceptTaskPlan", async () => {
    const fetchMock = mockFetchJson("{}");
    await acceptTaskPlan("plan-1");
    expect(firstCall(fetchMock)[0]).toContain("/task-plans/plan-1/commands/accept");
  });

  it("requestApproval", async () => {
    const fetchMock = mockFetchJson("{}");
    await requestApproval("cycle-1", {
      approval_type: "ACTION",
      subject_type: "task",
      subject_id: "task-1",
      subject_version: 1,
      subject_hash: "deadbeef",
    });
    const [url, init] = firstCall(fetchMock);
    expect(url).toContain("/delivery-cycles/cycle-1/approvals");
    expect(JSON.parse(init.body as string)).toMatchObject({
      approval_type: "ACTION",
      subject_id: "task-1",
      subject_version: 1,
      subject_hash: "deadbeef",
    });
  });

  it("createRelease", async () => {
    const fetchMock = mockFetchJson("{}");
    await createRelease("cycle-1");
    expect(firstCall(fetchMock)[0]).toContain("/delivery-cycles/cycle-1/release");
  });

  it("approveRelease", async () => {
    const fetchMock = mockFetchJson("{}");
    await approveRelease("rel-1");
    expect(firstCall(fetchMock)[0]).toContain("/releases/rel-1/approve");
  });

  it("executeRelease", async () => {
    const fetchMock = mockFetchJson("{}");
    await executeRelease("rel-1");
    expect(firstCall(fetchMock)[0]).toContain("/releases/rel-1/execute");
  });

  it("createOrchestratorSession", async () => {
    const fetchMock = mockFetchJson("{}");
    await createOrchestratorSession({
      project_id: "proj-1",
      delivery_cycle_id: "cycle-1",
    });
    const [url, init] = firstCall(fetchMock);
    expect(url).toContain("/orchestrator/sessions");
    expect(JSON.parse(init.body as string)).toEqual({
      project_id: "proj-1",
      delivery_cycle_id: "cycle-1",
    });
  });

  it("postOrchestratorTurn", async () => {
    const fetchMock = mockFetchJson('{"execution_id":"ex-1"}');
    await postOrchestratorTurn("sess-1", "Hello");
    const [url, init] = firstCall(fetchMock);
    expect(url).toContain("/orchestrator/sessions/sess-1/turns");
    expect(JSON.parse(init.body as string)).toEqual({ message: "Hello" });
  });
});
