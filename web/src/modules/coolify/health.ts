// Turning Coolify's statuses into "is anything wrong?", for the dashboard's
// Needs attention list and the status line on each team card.

import type { AppSummary, CourseSummary, SecurityInfo, TeamSummary } from "@/lib/types";

export type Health = "ok" | "warn" | "down" | "ignore";

/** "running:healthy" -> ok, "running:unhealthy" -> warn, "exited:..." -> down, "...:excluded" -> ignore. */
export function appHealth(app: AppSummary): Health {
  const [state, health, extra] = app.status.split(":");
  if (extra === "excluded" || state === "") return "ignore";
  if (state === "running") return health === "unhealthy" ? "warn" : "ok";
  if (state === "exited" || state === "stopped" || state === "restarting" || state === "degraded") {
    return "down";
  }
  return "warn";
}

export interface AttentionItem {
  /** red: broken or urgent; orange: should be looked at; gray: setup missing */
  level: "red" | "orange" | "gray";
  teamId: number;
  teamName: string;
  text: string;
}

const isProd = (name: string) => /\bprod/i.test(name);

/** "Update now", or anything with a vulnerability that's known to be exploited. */
export function isUrgent(s: SecurityInfo): boolean {
  return s.status === "update_now" || s.exploited_count > 0;
}

/** Everything a professor or TA should look at, most urgent first. */
export function attentionItems(summary: CourseSummary): AttentionItem[] {
  const items: AttentionItem[] = [];
  for (const t of summary.teams) {
    const add = (level: AttentionItem["level"], text: string) =>
      items.push({ level, teamId: t.team_id, teamName: t.team_name, text });
    if (!t.connected) {
      add("gray", "Not connected to Coolify yet");
      continue;
    }
    if (t.error) {
      add("gray", `Coolify couldn't be read: ${t.error}`);
      continue;
    }
    for (const app of t.apps) {
      const health = appHealth(app);
      const state = app.status.split(":")[0];
      if (health === "down") {
        add(
          isProd(app.name) ? "red" : "orange",
          `${app.name} is ${state === "exited" ? "stopped" : state}`,
        );
      } else if (health === "warn") {
        add("orange", `${app.name} is unhealthy`);
      }
      const s = app.security;
      if (s && isUrgent(s)) {
        const counts = [
          s.critical_count && `${s.critical_count} critical`,
          s.high_count && `${s.high_count} high`,
        ]
          .filter(Boolean)
          .join(", ");
        const what =
          s.status === "update_now"
            ? "security update needed"
            : `${s.exploited_count} known-exploited vulnerabilit${s.exploited_count === 1 ? "y" : "ies"}`;
        add("red", `${app.name}: ${what}${counts ? ` (${counts})` : ""}`);
      }
    }
    for (const server of t.servers) {
      if (server.reachable === false) add("red", `Server ${server.name} isn't reachable`);
      if ((server.security_count ?? 0) > 0) {
        add("orange", `Server ${server.name}: ${server.security_count} security update(s) waiting`);
      }
      if (server.reboot_required) add("orange", `Server ${server.name} needs a reboot`);
    }
  }
  const rank = { red: 0, orange: 1, gray: 2 };
  return items.sort((a, b) => rank[a.level] - rank[b.level]);
}

/** One line for a team card: how many apps are up, and the worst security verdict. */
export function teamHealth(t: TeamSummary) {
  const apps = t.apps.filter((a) => appHealth(a) !== "ignore");
  const up = apps.filter((a) => appHealth(a) === "ok").length;
  const down = apps.filter((a) => appHealth(a) === "down").length;
  const urgent = t.apps.filter((a) => a.security && isUrgent(a.security)).length;
  const updates = t.apps.filter(
    (a) => a.security?.status === "update_available" && !isUrgent(a.security),
  ).length;
  return { total: apps.length, up, down, urgent, updates };
}
