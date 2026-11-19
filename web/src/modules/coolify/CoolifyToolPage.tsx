"use client";

// Placeholder for the Coolify tool. Replace with real screens as features land.

import { ToolPlaceholder } from "@/components/ToolPlaceholder";

export function CoolifyToolPage() {
  return (
    <ToolPlaceholder
      toolId="coolify"
      title="Coolify"
      intro="Deploy each team's project to the course's Coolify server and keep an eye on it."
      planned={[
        "Create one Coolify project per team, with standard environments",
        "Deploy each team's app from its GitHub repo",
        "Set environment variables in bulk from a course template",
        "Deployment overview: status, last deploy, and live URL for every team",
      ]}
    />
  );
}
