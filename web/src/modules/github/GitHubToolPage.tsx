"use client";

// Placeholder for the GitHub tool. Replace with real screens as features land.

import { ToolPlaceholder } from "@/components/ToolPlaceholder";

export function GitHubToolPage() {
  return (
    <ToolPlaceholder
      toolId="github"
      title="GitHub"
      intro="Bulk setup and an overview of the course's GitHub organization."
      planned={[
        "Create project repos in bulk from a template, with branch protection and labels",
        "Create teams and add students from a roster CSV",
        "Give teams access to their project repos",
        "Org overview: repos, teams, members, and pending invitations",
      ]}
    />
  );
}
