"use client";

// Placeholder for the Linear tool. Replace with real screens as features land.

import { ToolPlaceholder } from "@/components/ToolPlaceholder";

export function LinearToolPage() {
  return (
    <ToolPlaceholder
      toolId="linear"
      title="Linear"
      intro="Set up Linear teams and projects for each group, and track their progress."
      planned={[
        "Invite users and create one team per project group",
        "Create projects, starting issues, and workflow states from course templates",
        "Monitor activity, issue throughput, and stalled projects",
      ]}
    />
  );
}
