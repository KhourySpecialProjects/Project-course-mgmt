"use client";

// Every team at a glance, for spotting quiet teams: when they last pushed, their
// open and recently merged pull requests, and their Linear progress. Each row
// opens the team's Updates page.

import {
  Anchor,
  Badge,
  Button,
  Group,
  Skeleton,
  Stack,
  Table,
  Text,
  Title,
  Tooltip,
} from "@mantine/core";
import { IconAlertTriangle, IconRefresh } from "@tabler/icons-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { api } from "@/lib/api";
import { timeAgo } from "@/lib/format";
import type { LinearUpdates, RepoUpdates, Team } from "@/lib/types";

interface Row {
  team: Team;
  repos: RepoUpdates[] | null;
  linear: LinearUpdates | null;
}

const DAY = 86400 * 1000;
const COULD_NOT_LOAD: LinearUpdates = {
  error: "Couldn't load Linear.",
  name: null,
  key: null,
  url: null,
  counts: {},
  issues: [],
};

export function TeamActivity() {
  const [rows, setRows] = useState<Row[] | null>(null);
  const [version, setVersion] = useState(0);
  // When the list was loaded, for "this week" and "stale".
  const [loadedAt, setLoadedAt] = useState(0);

  useEffect(() => {
    let cancelled = false;
    const update = (id: number, changes: Partial<Row>) => {
      if (cancelled) return;
      setRows((list) => list?.map((r) => (r.team.id === id ? { ...r, ...changes } : r)) ?? null);
    };
    api
      .get<Team[]>("/teams")
      .then((teams) => {
        if (cancelled) return;
        setRows(teams.map((team) => ({ team, repos: null, linear: null })));
        setLoadedAt(Date.now());
        for (const t of teams) {
          api
            .get<RepoUpdates[]>(`/tools/github/teams/${t.id}/updates`)
            .then((repos) => update(t.id, { repos }))
            .catch(() => update(t.id, { repos: [] }));
          api
            .get<LinearUpdates>(`/tools/linear/teams/${t.id}/updates`)
            .then((linear) => update(t.id, { linear }))
            .catch(() => update(t.id, { linear: COULD_NOT_LOAD }));
        }
      })
      .catch(() => !cancelled && setRows([]));
    return () => {
      cancelled = true;
    };
  }, [version]);

  return (
    <Stack gap="lg">
      <Group justify="space-between" align="flex-end">
        <div>
          <Title order={2}>Team activity</Title>
          <Text c="dimmed">
            Every team&apos;s recent work in GitHub and Linear. Open a team for the details.
          </Text>
        </div>
        <Button
          variant="default"
          leftSection={<IconRefresh size={16} />}
          onClick={() => setVersion((v) => v + 1)}
        >
          Refresh
        </Button>
      </Group>

      {rows === null ? (
        <Skeleton h={240} />
      ) : rows.length === 0 ? (
        <Text c="dimmed">No teams yet.</Text>
      ) : (
        <Table.ScrollContainer minWidth={820}>
          <Table highlightOnHover verticalSpacing="sm">
            <Table.Thead>
              <Table.Tr>
                <Table.Th>Team</Table.Th>
                <Table.Th>Last commit</Table.Th>
                <Table.Th>Pull requests</Table.Th>
                <Table.Th>Linear</Table.Th>
                <Table.Th>Can&apos;t see</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {rows.map((r) => (
                <ActivityRow key={r.team.id} row={r} now={loadedAt} />
              ))}
            </Table.Tbody>
          </Table>
        </Table.ScrollContainer>
      )}
    </Stack>
  );
}

function ActivityRow({ row: { team, repos, linear }, now }: { row: Row; now: number }) {
  const readable = (repos ?? []).filter((r) => !r.error);
  const commitDates = readable
    .flatMap((r) => r.commits.map((c) => c.date))
    .filter(Boolean)
    .sort();
  const last = commitDates[commitDates.length - 1];
  const stale = last ? now - new Date(last).getTime() > 7 * DAY : false;
  const open = readable.reduce((n, r) => n + r.open_pulls.length, 0);
  const merged = readable.reduce(
    (n, r) =>
      n + r.recent_merged.filter((p) => now - new Date(p.updated_at).getTime() < 7 * DAY).length,
    0,
  );
  const blocked = [
    ...(repos ?? []).filter((r) => r.error).map((r) => ({ what: r.full_name, why: r.error ?? "" })),
    ...(linear?.error ? [{ what: "Linear", why: linear.error }] : []),
  ];
  const doneThisWeek = (linear?.issues ?? []).filter(
    (i) => i.completed_at && now - new Date(i.completed_at).getTime() < 7 * DAY,
  ).length;

  return (
    <Table.Tr>
      <Table.Td>
        <Anchor component={Link} href={`/teams/${team.id}/updates`} fw={500}>
          {team.name}
        </Anchor>
      </Table.Td>
      <Table.Td>
        {repos === null ? (
          <Skeleton h={18} w={90} />
        ) : last ? (
          <Badge variant="light" color={stale ? "orange" : "teal"}>
            {timeAgo(last)}
          </Badge>
        ) : (
          <Text size="sm" c="dimmed">
            —
          </Text>
        )}
      </Table.Td>
      <Table.Td>
        {repos === null ? (
          <Skeleton h={18} w={120} />
        ) : (
          <Text size="sm">
            {open} open · {merged} merged this week
          </Text>
        )}
      </Table.Td>
      <Table.Td>
        {linear === null ? (
          <Skeleton h={18} w={120} />
        ) : linear.error ? (
          <Text size="sm" c="dimmed">
            —
          </Text>
        ) : (
          <Text size="sm">
            {doneThisWeek} done this week · {linear.counts.started ?? 0} in progress
          </Text>
        )}
      </Table.Td>
      <Table.Td>
        {blocked.length > 0 && (
          <Tooltip
            multiline
            maw={420}
            label={blocked.map((b) => `${b.what}: ${b.why}`).join(" · ")}
          >
            <Badge color="orange" variant="light" leftSection={<IconAlertTriangle size={12} />}>
              {blocked.map((b) => b.what.split("/").pop()).join(", ")}
            </Badge>
          </Tooltip>
        )}
      </Table.Td>
    </Table.Tr>
  );
}
