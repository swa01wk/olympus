import type { World } from "../../engine/world";
import { SHAS } from "../shas";
import { fid } from "../../engine/deterministic-id";
import type { CodeEntity, CodeRelation } from "@/lib/contracts/entity-types";

const TREE = [
  "app/main.py",
  "app/api/tickets.py",
  "app/services/ticket_service.py",
  "app/repositories/ticket_repository.py",
  "app/models/ticket.py",
  "app/schemas/ticket.py",
  "tests/test_create_ticket.py",
  "tests/test_ticket_status.py",
  "tests/test_priority.py",
];

/** Adds realistic SupportDesk file tree + route path to canonical index when sparse. */
export function enrichCodeModel(world: World) {
  const canonical = world.indexVersions.find(
    (v) => v.id === world.indexPointer.canonical_index_version_id || v.kind === "CANONICAL",
  );
  if (!canonical) return;

  const hasRealFiles = world.codeEntities.some((e) => e.file_path === "app/api/tickets.py");
  if (hasRealFiles) return;

  const entities: CodeEntity[] = [];
  const relations: CodeRelation[] = [];
  let n = 0;

  const add = (partial: Omit<CodeEntity, "id" | "index_version_id" | "language">) => {
    n += 1;
    const id = fid("entity", `${canonical.key ?? canonical.id}:${partial.stable_key}`);
    entities.push({
      id,
      index_version_id: canonical.id,
      language: "python",
      ...partial,
    });
    return id;
  };

  const repoId = add({
    stable_key: "py:supportdesk",
    type: "REPOSITORY",
    name: "supportdesk",
    file_path: null,
  });

  const fileIds: Record<string, string> = {};
  for (const path of TREE) {
    fileIds[path] = add({
      stable_key: `py:${path}`,
      type: "FILE",
      name: path.split("/").pop()!,
      file_path: path,
      start_line: 1,
      end_line: 80,
    });
    relations.push({
      id: fid("rel", `contains-${path}`),
      index_version_id: canonical.id,
      from_entity_id: repoId,
      to_entity_id: fileIds[path]!,
      relation: "CONTAINS",
      provenance: "AST",
      confidence: 1,
    });
  }

  const routeId = add({
    stable_key: "py:app/api/tickets.py::POST /tickets",
    type: "ROUTE",
    name: "POST /tickets",
    qualified_name: "POST /tickets",
    file_path: "app/api/tickets.py",
    start_line: 12,
    end_line: 18,
  });

  const handlerId = add({
    stable_key: "py:app/api/tickets.py::create_ticket",
    type: "FUNCTION",
    name: "create_ticket",
    file_path: "app/api/tickets.py",
    start_line: 12,
    end_line: 18,
  });

  const serviceMethodId = add({
    stable_key: "py:app/services/ticket_service.py::TicketService.create_ticket",
    type: "METHOD",
    name: "TicketService.create_ticket",
    qualified_name: "TicketService.create_ticket",
    file_path: "app/services/ticket_service.py",
    start_line: 20,
    end_line: 35,
  });

  const repoMethodId = add({
    stable_key: "py:app/repositories/ticket_repository.py::TicketRepository.create",
    type: "METHOD",
    name: "TicketRepository.create",
    file_path: "app/repositories/ticket_repository.py",
    start_line: 10,
    end_line: 22,
  });

  const ormId = add({
    stable_key: "py:app/models/ticket.py::Ticket",
    type: "ORM_MODEL",
    name: "Ticket",
    file_path: "app/models/ticket.py",
    start_line: 8,
    end_line: 40,
  });

  const testId = add({
    stable_key: "py:tests/test_create_ticket.py::test_create_ticket",
    type: "TEST",
    name: "test_create_ticket",
    file_path: "tests/test_create_ticket.py",
    start_line: 5,
    end_line: 20,
  });

  const chain: Array<[string, string, string]> = [
    [routeId, handlerId, "CALLS"],
    [handlerId, serviceMethodId, "CALLS"],
    [serviceMethodId, repoMethodId, "CALLS"],
    [repoMethodId, ormId, "ACCESSES"],
    [testId, routeId, "VERIFIED_BY"],
  ];

  for (const [from, to, rel] of chain) {
    relations.push({
      id: fid("rel", `${from}-${rel}-${to}`),
      index_version_id: canonical.id,
      from_entity_id: from,
      to_entity_id: to,
      relation: rel,
      provenance: rel === "VERIFIED_BY" ? "FRAMEWORK:pytest" : "AST",
      confidence: 1,
    });
  }

  canonical.commit_sha = canonical.commit_sha || SHAS.r1Integrated;
  world.codeEntities.push(...entities);
  world.codeRelations.push(...relations);

  world.sampleLineage = {
    root_type: "METHOD",
    root_id: serviceMethodId,
    direction: "REVERSE",
    nodes: [
      { type: "METHOD", id: serviceMethodId, label: "TicketService.create_ticket" },
      { type: "FEATURE_SPEC", id: fid("fs", "FS-001"), key: "FS-001", label: "Ticket management", version: 1 },
      { type: "RELEASE", id: world.releases[0]?.id ?? fid("rel", "R1"), key: "R1", label: "Release R1" },
    ],
    edges: [
      { from: fid("fs", "FS-001"), to: serviceMethodId, relation: "IMPLEMENTS", origin: "GENERATED_LINEAGE" },
    ],
  };
}
