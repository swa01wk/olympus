import type { CodeEntity, CodeRelation, CodeIndexVersion } from "@/lib/contracts/entity-types";
import { fid } from "../../engine/deterministic-id";
import { SUPPORTDESK_TREE, revisionExtraFiles, type RevisionLabel } from "./revisions";

export function emitSupportDeskIndex(
  version: CodeIndexVersion,
  label: RevisionLabel,
): { entities: CodeEntity[]; relations: CodeRelation[] } {
  const entities: CodeEntity[] = [];
  const relations: CodeRelation[] = [];
  const paths = [...SUPPORTDESK_TREE, ...revisionExtraFiles(label)];

  const add = (partial: Omit<CodeEntity, "id" | "index_version_id" | "language">) => {
    const id = fid("entity", `${version.key ?? version.id}:${partial.stable_key}`);
    entities.push({
      id,
      index_version_id: version.id,
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
  for (const path of paths) {
    fileIds[path] = add({
      stable_key: `py:${path}`,
      type: "FILE",
      name: path.split("/").pop()!,
      file_path: path,
      start_line: 1,
      end_line: 80,
    });
    relations.push({
      id: fid("rel", `${version.id}-contains-${path}`),
      index_version_id: version.id,
      from_entity_id: repoId,
      to_entity_id: fileIds[path]!,
      relation: "CONTAINS",
      provenance: "AST",
      confidence: 1,
    });
  }

  add({
    stable_key: "py:app/services/ticket_service.py::TicketService.create_ticket",
    type: "METHOD",
    name: "TicketService.create_ticket",
    qualified_name: "TicketService.create_ticket",
    file_path: "app/services/ticket_service.py",
    start_line: 20,
    end_line: 35,
  });

  if (label !== "R1") {
    add({
      stable_key: "py:app/models/priority.py::Priority",
      type: "ORM_MODEL",
      name: "Priority",
      file_path: "app/models/priority.py",
      start_line: 1,
      end_line: 24,
    });
  }

  return { entities, relations };
}
