import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { RepositoryHeader } from "@/components/repository/RepositoryHeader";

describe("RepositoryHeader", () => {
  it("shows CONNECTED without credential secret", () => {
    render(
      <RepositoryHeader
        repository={{
          id: "r1",
          project_id: "p1",
          key: "REPO-001",
          name: "supportdesk",
          source_type: "EXTERNAL_CLONE",
          provider: "GITHUB",
          remote_url: "https://github.com/acme/supportdesk",
          default_branch: "main",
          status: "READY",
          workspace_id: "w1",
          credential_status: "CONFIGURED",
          credential_ref: "env:SECRET",
        }}
        workspace={null}
        canonicalIndex={null}
      />,
    );
    expect(screen.getByText("CONNECTED")).toBeTruthy();
    expect(screen.queryByText(/env:SECRET/)).toBeNull();
  });
});
