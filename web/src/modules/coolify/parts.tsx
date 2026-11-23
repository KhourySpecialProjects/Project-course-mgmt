"use client";

// Small pieces shared by the team Coolify panel and the course-wide Security page.

import { Badge, Code, Group, Loader, ScrollArea, Stack, Table, Text, Tooltip } from "@mantine/core";
import { useEffect, useState } from "react";

import { api } from "@/lib/api";
import { formatDateTime } from "@/lib/format";
import type { SecurityInfo, ServerJob } from "@/lib/types";

export const errorMessage = (err: unknown) => (err instanceof Error ? err.message : String(err));

/** "running:healthy" -> Running (green), "exited:unhealthy" -> Stopped, ... */
export function ResourceStatus({ status }: { status: string }) {
  const [state, health] = status.split(":");
  const map: Record<string, [string, string]> = {
    running: ["Running", health === "unhealthy" ? "yellow" : "teal"],
    exited: ["Stopped", "gray"],
    stopped: ["Stopped", "gray"],
    restarting: ["Restarting", "yellow"],
    starting: ["Starting", "blue"],
    degraded: ["Degraded", "orange"],
  };
  const [label, color] = map[state] ?? [state || "Unknown", "gray"];
  return (
    <Tooltip label={status || "Unknown"} disabled={!status}>
      <Badge variant="dot" color={color}>
        {label}
        {health === "unhealthy" && state === "running" ? " (unhealthy)" : ""}
      </Badge>
    </Tooltip>
  );
}

const SECURITY: Record<string, [string, string]> = {
  update_now: ["Update now", "red"],
  update_available: ["Update available", "orange"],
  no_fix: ["No fix yet", "yellow"],
  check_needed: ["Check needed", "gray"],
  ok: ["OK", "teal"],
  not_checked: ["Not scanned", "gray"],
};

/** Order for sorting: most urgent first. */
export const SECURITY_RANK: Record<string, number> = {
  update_now: 0,
  update_available: 1,
  no_fix: 2,
  check_needed: 3,
  not_checked: 4,
  ok: 5,
};

export function SecurityBadge({ security }: { security: SecurityInfo | null }) {
  if (!security) {
    return (
      <Badge variant="light" color="gray">
        No scan
      </Badge>
    );
  }
  const [label, color] = SECURITY[security.status] ?? [security.label || security.status, "gray"];
  const counts = [
    security.critical_count && `${security.critical_count} critical`,
    security.high_count && `${security.high_count} high`,
    security.medium_count && `${security.medium_count} medium`,
  ].filter(Boolean);
  const tip = [counts.join(", "), security.action].filter(Boolean).join(" · ");
  return (
    <Tooltip label={tip} disabled={!tip} multiline maw={320}>
      <Group gap={4} wrap="nowrap">
        <Badge variant="light" color={color}>
          {security.label || label}
        </Badge>
        {security.exploited_count > 0 && (
          <Badge variant="filled" color="red" size="sm">
            {security.exploited_count} exploited
          </Badge>
        )}
      </Group>
    </Tooltip>
  );
}

export function SeverityBadge({ severity }: { severity: string }) {
  const color =
    { critical: "red", high: "orange", medium: "yellow", low: "blue" }[severity.toLowerCase()] ??
    "gray";
  return (
    <Badge color={color} variant="light" size="sm">
      {severity}
    </Badge>
  );
}

export const JOB_LABELS: Record<string, string> = {
  patch_check: "Update check",
  patch_security: "Security updates",
  patch_all: "All updates",
  image_scan: "Container scan",
};

/** Keeps a running job up to date until it finishes, then calls onDone once. */
export function useJob(teamId: number, initial: ServerJob, onDone?: (job: ServerJob) => void) {
  const [job, setJob] = useState(initial);
  useEffect(() => {
    if (job.status !== "running") return;
    const timer = setTimeout(() => {
      api
        .get<ServerJob>(`/tools/coolify/teams/${teamId}/jobs/${job.id}`)
        .then((next) => {
          setJob(next);
          if (next.status !== "running") onDone?.(next);
        })
        .catch(() => setJob((j) => ({ ...j })));
    }, 2000);
    return () => clearTimeout(timer);
  }, [job, teamId, onDone]);
  return job;
}

export function JobStatusBadge({ job }: { job: ServerJob }) {
  if (job.status === "running") {
    return (
      <Badge color="blue" variant="light" leftSection={<Loader size={10} color="blue" />}>
        Running
      </Badge>
    );
  }
  return (
    <Badge color={job.status === "succeeded" ? "teal" : "red"} variant="light">
      {job.status === "succeeded" ? "Done" : "Failed"}
    </Badge>
  );
}

/** Patch check result in one line: "35 updates, 12 security · reboot needed". */
export function PatchSummary({ job }: { job: ServerJob }) {
  const r = job.result;
  if (!r || r.update_count === undefined) return null;
  return (
    <Group gap={6}>
      <Badge color={r.security_count ? "red" : r.update_count ? "yellow" : "teal"} variant="light">
        {r.update_count === 0
          ? "Up to date"
          : `${r.update_count} update${r.update_count === 1 ? "" : "s"}, ${r.security_count} security`}
      </Badge>
      {r.reboot_required && (
        <Badge color="orange" variant="outline">
          Reboot needed
        </Badge>
      )}
    </Group>
  );
}

/** A finished (or running) job: what happened, the log, and what it found. */
export function JobDetails({ job }: { job: ServerJob }) {
  const images = job.result?.images ?? [];
  const updates = job.result?.updates ?? [];
  return (
    <Stack gap="sm">
      <Group gap="xs">
        <Text fw={500}>{JOB_LABELS[job.kind] ?? job.kind}</Text>
        <JobStatusBadge job={job} />
        <Text size="xs" c="dimmed">
          {job.server_name} · {formatDateTime(job.created_at)}
          {job.started_by ? ` · by ${job.started_by}` : ""}
        </Text>
      </Group>
      {job.error && (
        <Text size="sm" c="red">
          {job.error}
        </Text>
      )}
      <PatchSummary job={job} />
      {updates.length > 0 && (
        <ScrollArea.Autosize mah={220}>
          <Table striped withTableBorder fz="xs">
            <Table.Thead>
              <Table.Tr>
                <Table.Th>Package</Table.Th>
                <Table.Th>From</Table.Th>
                <Table.Th>To</Table.Th>
                <Table.Th />
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {updates.map((u) => (
                <Table.Tr key={u.package}>
                  <Table.Td>{u.package}</Table.Td>
                  <Table.Td>{u.current_version}</Table.Td>
                  <Table.Td>{u.new_version}</Table.Td>
                  <Table.Td>
                    {u.security && (
                      <Badge color="red" size="xs" variant="light">
                        security
                      </Badge>
                    )}
                  </Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </ScrollArea.Autosize>
      )}
      {images.map((img) => (
        <Stack key={img.image} gap={4}>
          <Group gap="xs">
            <Code>{img.image}</Code>
            {img.counts && (
              <>
                <Badge color="red" variant="light" size="sm">
                  {img.counts.critical ?? 0} critical
                </Badge>
                <Badge color="orange" variant="light" size="sm">
                  {img.counts.high ?? 0} high
                </Badge>
                <Text size="xs" c="dimmed">
                  {img.counts.medium ?? 0} medium · {img.fixable ?? 0} fixable
                </Text>
              </>
            )}
            {img.error && (
              <Text size="xs" c="red">
                {img.error}
              </Text>
            )}
          </Group>
          {(img.findings ?? []).slice(0, 8).map((f) => (
            <Text key={`${img.image}-${f.id}-${f.package}`} size="xs" c="dimmed" pl="md">
              {f.severity} · {f.id} · {f.package} {f.version}
              {f.fixed_in ? ` → fixed in ${f.fixed_in}` : " (no fix yet)"}
            </Text>
          ))}
        </Stack>
      ))}
      {job.log && (
        <ScrollArea.Autosize mah={260}>
          <Code block fz="xs">
            {job.log}
          </Code>
        </ScrollArea.Autosize>
      )}
    </Stack>
  );
}

/**
 * Ask the workbench to connect a team to its Coolify team (making the team's own
 * token). Fire-and-forget: used right after a team or its Coolify link is added.
 * Needs a Coolify admin token; without one this quietly does nothing.
 */
export function connectCoolifyInBackground(teamId: number) {
  api.post(`/tools/coolify/teams/${teamId}/connect`).catch(() => undefined);
}
