import type {
  CodeEntity,
  CodeIndexVersion,
  CodeRelation,
  IndexPointer,
} from "@/lib/contracts/entity-types";
import type { z } from "zod";
import type { EntityType } from "@/lib/contracts/code-intelligence";
import { IDS, SHAS } from "./ids";

const ENTITY_TYPES: z.infer<typeof EntityType>[] = [
  "REPOSITORY",
  "PACKAGE",
  "MODULE",
  "FILE",
  "CLASS",
  "METHOD",
  "FUNCTION",
  "ROUTE",
  "SCHEMA",
  "ORM_MODEL",
  "TABLE",
  "TEST",
];

function entityUuid(n: number) {
  return `11111111-1111-4111-8111-${(0xce000 + n).toString(16).padStart(12, "0")}`;
}

export function buildCodeIndex() {
  const indexVersions: CodeIndexVersion[] = [
    {
      id: IDS.idxCanonicalR1,
      repository_id: IDS.repo,
      commit_sha: SHAS.r1Integrated,
      kind: "CANONICAL",
      source: "INTEGRATION",
      scope_ref: "IC-001",
      status: "READY",
    },
    {
      id: IDS.idxCandidate551,
      repository_id: IDS.repo,
      commit_sha: SHAS.candidate551,
      kind: "CANDIDATE",
      source: "EXECUTION",
      scope_ref: "EX-551",
      status: "READY",
    },
    {
      id: IDS.idxCandidate552,
      repository_id: IDS.repo,
      commit_sha: SHAS.candidate552,
      kind: "CANDIDATE",
      source: "EXECUTION",
      scope_ref: "EX-552",
      status: "READY",
    },
    {
      id: IDS.idxCanonicalIc004,
      repository_id: IDS.repo,
      commit_sha: SHAS.dc004Integrated,
      kind: "CANONICAL",
      source: "INTEGRATION",
      scope_ref: "IC-004",
      status: "READY",
    },
  ];

  const pointer: IndexPointer = {
    repository_id: IDS.repo,
    canonical_index_version_id: IDS.idxCanonicalR1,
    released_commit_sha: SHAS.r1Integrated,
  };

  const codeEntities: CodeEntity[] = [];
  const codeRelations: CodeRelation[] = [];
  let n = 0;

  for (const version of indexVersions) {
    for (const type of ENTITY_TYPES) {
      n += 1;
      const id = entityUuid(n);
      const slug = type.toLowerCase().replace("_", "-");
      codeEntities.push({
        id,
        index_version_id: version.id,
        stable_key: `supportdesk::${version.scope_ref}::${slug}-${n}`,
        type,
        language: "python",
        name: `${type}_${n}`,
        qualified_name: `supportdesk.${slug}_${n}`,
        file_path:
          type === "REPOSITORY" || type === "PACKAGE"
            ? null
            : `app/${slug.replace("-", "_")}_${n}.py`,
        start_line: type === "FILE" ? null : 1,
        end_line: type === "FILE" ? null : 40,
      });
    }
  }

  for (let extra = 0; extra < 12; extra += 1) {
    n += 1;
    codeEntities.push({
      id: entityUuid(n),
      index_version_id: IDS.idxCanonicalR1,
      stable_key: `supportdesk::supporting::helper-${extra + 1}`,
      type: extra % 2 === 0 ? "FUNCTION" : "METHOD",
      language: "python",
      name: `helper_${extra + 1}`,
      file_path: `app/support/helper_${extra + 1}.py`,
      start_line: 1,
      end_line: 20,
    });
  }

  // Structural edges between adjacent entities per index version
  for (const version of indexVersions) {
    const inVersion = codeEntities.filter((e) => e.index_version_id === version.id);
    for (let i = 1; i < inVersion.length; i += 1) {
      codeRelations.push({
        id: entityUuid(10_000 + codeRelations.length + 1),
        index_version_id: version.id,
        from_entity_id: inVersion[i - 1]!.id,
        to_entity_id: inVersion[i]!.id,
        relation: "CONTAINS",
      });
    }
  }

  return { indexVersions, pointer, codeEntities, codeRelations };
}
