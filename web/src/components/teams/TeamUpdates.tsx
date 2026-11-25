"use client";

// One team's recent work: commits and pull requests in its GitHub repositories (the
// one linked on its card plus the ones its Coolify apps deploy from) and its Linear
// issues. Read-only.

import {
  Alert,
  Anchor,
  Badge,
  Button,
  Card,
  Group,
  Progress,
  SimpleGrid,
  Skeleton,
  Stack,
  Table,
  Text,
  Title,
  Tooltip,
} from "@mantine/core";
import {
  IconAlertTriangle,
  IconArrowLeft,
  IconBrandGithub,
  IconLayoutKanban,
  IconLock,
  IconRefresh,
} from "@tabler/icons-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { api } from "@/lib/api";
import { timeAgo } from "@/lib/format";
import type { LinearUpdates, PullInfo, RepoUpdates, Team } from "@/lib/types";

const errorMessage = (err: unknown) => (err instanceof Error ? err.message : String(err));

export function TeamUpdates({
  teamId,
  embedded = false,
}: {
  teamId: number;
  /** Shown inside the team's page: leave out the page title. */
  embedded?: boolean;
}) {
  const [team, setTeam] = useState<Team | null>(null);
  const [repos, setRepos] = useState<RepoUpdates[] | null>(null);
  const [linear, setLinear] = useState<LinearUpdates | null>(null);
  // When the Linear data arrived, for "done this week".
  const [loadedAt, setLoadedAt] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [version, setVersion] = useState(0);

  useEffect(() => {
    let cancelled = false;
    api
      .get<Team[]>("/teams")
      .then((all) => !cancelled && setTeam(all.find((t) => t.id === teamId) ?? null))
      .catch((err) => !cancelled && setError(errorMessage(err)));
    api
      .get<RepoUpdates[]>(`/tools/github/teams/${teamId}/updates`)
      .then((r) => !cancelled && setRepos(r))
      .catch((err) => !cancelled && setError(errorMessage(err)));
    api
      .get<LinearUpdates>(`/tools/linear/teams/${teamId}/updates`)
      .then((r) => {
        if (cancelled) return;
        setLinear(r);
        setLoadedAt(Date.now());
      })
      .catch((err) => !cancelled && setError(errorMessage(err)));
    return () => {
      cancelled = true;
    };
  }, [teamId, version]);

  return (
    <Stack gap="lg">
      <Group justify="space-between" align="flex-start">
        {embedded ? (
          <Text c="dimmed" size="sm">
            Recent commits and pull requests, and Linear progress.
          </Text>
        ) : (
          <div>
            <Anchor component={Link} href={`/teams/${teamId}`} size="sm" c="dimmed">
              <Group gap={4}>
                <IconArrowLeft size={14} /> {team?.name ?? "Team"}
              </Group>
            </Anchor>
            <Title order={2}>{team?.name ?? "Team"} · Updates</Title>
            <Text c="dimmed" size="sm">
              Recent commits and pull requests, and Linear progress.
            </Text>
          </div>
        )}
        <Button
          variant="default"
          leftSection={<IconRefresh size={16} />}
          onClick={() => {
            setRepos(null);
            setLinear(null);
            setVersion((v) => v + 1);
          }}
        >
          Refresh
        </Button>
      </Group>

      {error && (
        <Alert color="red" icon={<IconAlertTriangle />}>
          {error}
        </Alert>
      )}

      <Stack gap="sm">
        <Group gap="xs">
          <IconBrandGithub size={20} />
          <Title order={4}>GitHub</Title>
        </Group>
        {repos === null ? (
          <Skeleton h={160} />
        ) : repos.length === 0 ? (
          <Text size="sm" c="dimmed">
            No repositories yet: link one on the team&apos;s card, or connect its Coolify (its
            apps&apos; repositories are added here automatically).
          </Text>
        ) : (
          <>
            {team && <StudentActivity team={team} repos={repos} />}
            {repos.map((r) => (
              <RepoCard key={r.full_name} repo={r} />
            ))}
          </>
        )}
      </Stack>

      <Stack gap="sm">
        <Group gap="xs">
          <IconLayoutKanban size={20} />
          <Title order={4}>Linear</Title>
        </Group>
        {linear === null ? <Skeleton h={160} /> : <LinearCard linear={linear} now={loadedAt} />}
      </Stack>
    </Stack>
  );
}

/**
 * Each student's recent work, matched by GitHub username: commits and open pull
 * requests in the team's readable repositories (the last 30 commits of each).
 */
function StudentActivity({ team, repos }: { team: Team; repos: RepoUpdates[] }) {
  const readable = repos.filter((r) => !r.error);
  if (team.members.length === 0 || readable.length === 0) return null;
  const commits = readable.flatMap((r) => r.commits);
  const pulls = readable.flatMap((r) => r.open_pulls);
  const known = new Set(team.members.map((m) => m.github_username.toLowerCase()).filter(Boolean));
  const strangers = [
    ...new Set(
      [...commits.map((c) => c.author), ...pulls.map((p) => p.author)].filter(
        (a) => a && !known.has(a.toLowerCase()) && !a.endsWith("[bot]"),
      ),
    ),
  ];

  return (
    <Card withBorder>
      <Stack gap="xs">
        <Text fw={600}>By student</Text>
        <Table fz="sm" verticalSpacing={4}>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>Student</Table.Th>
              <Table.Th>Last commit</Table.Th>
              <Table.Th>Recent commits</Table.Th>
              <Table.Th>Open PRs</Table.Th>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {team.members.map((m) => {
              const login = m.github_username.toLowerCase();
              const mine = login ? commits.filter((c) => c.author.toLowerCase() === login) : [];
              const last = mine
                .map((c) => c.date)
                .sort()
                .pop();
              const prs = login ? pulls.filter((p) => p.author.toLowerCase() === login).length : 0;
              return (
                <Table.Tr key={m.id}>
                  <Table.Td>
                    <Text size="sm" fw={500}>
                      {m.name}
                    </Text>
                    {!m.github_username && (
                      <Text size="xs" c="dimmed">
                        add their GitHub username to see this
                      </Text>
                    )}
                  </Table.Td>
                  <Table.Td>
                    {last ? (
                      timeAgo(last)
                    ) : (
                      <Text size="sm" c={m.github_username ? "orange" : "dimmed"}>
                        {m.github_username ? "none recently" : "—"}
                      </Text>
                    )}
                  </Table.Td>
                  <Table.Td>{m.github_username ? mine.length : "—"}</Table.Td>
                  <Table.Td>{m.github_username ? prs : "—"}</Table.Td>
                </Table.Tr>
              );
            })}
          </Table.Tbody>
        </Table>
        {strangers.length > 0 && (
          <Text size="xs" c="dimmed">
            Also committing, but not on the team&apos;s list: {strangers.join(", ")}.
          </Text>
        )}
      </Stack>
    </Card>
  );
}

function RepoCard({ repo: r }: { repo: RepoUpdates }) {
  return (
    <Card withBorder>
      <Stack gap="sm">
        <Group justify="space-between" align="flex-start">
          <div>
            <Group gap={6}>
              <Anchor
                href={r.url ?? `https://github.com/${r.full_name}`}
                target="_blank"
                rel="noopener noreferrer"
                fw={600}
              >
                {r.full_name}
              </Anchor>
              {r.private && (
                <Tooltip label="Private repository">
                  <IconLock size={14} />
                </Tooltip>
              )}
            </Group>
            <Text size="xs" c="dimmed">
              {r.source}
              {r.branch ? ` · showing ${r.branch}` : ""}
            </Text>
          </div>
          {!r.error && (
            <Group gap={6}>
              <Badge variant="light" color={r.pushed_at ? "blue" : "gray"}>
                pushed {timeAgo(r.pushed_at) || "never"}
              </Badge>
              <Badge variant="light" color="gray">
                {r.open_pulls.length} open PR{r.open_pulls.length === 1 ? "" : "s"}
              </Badge>
              <Badge variant="light" color="gray">
                {r.open_issues} open issue{r.open_issues === 1 ? "" : "s"}
              </Badge>
            </Group>
          )}
        </Group>

        {r.error ? (
          <Alert color="orange" icon={<IconAlertTriangle />} p="xs">
            {r.error}
          </Alert>
        ) : (
          <SimpleGrid cols={{ base: 1, md: 2 }}>
            <Stack gap={4}>
              <Text size="sm" fw={500}>
                Latest commits
              </Text>
              {r.commits.length === 0 ? (
                <Text size="sm" c="dimmed">
                  No commits.
                </Text>
              ) : (
                r.commits.slice(0, 8).map((c) => (
                  <Group key={c.sha} gap={6} wrap="nowrap">
                    <Anchor
                      href={c.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      size="xs"
                      ff="monospace"
                    >
                      {c.sha}
                    </Anchor>
                    <Text size="sm" lineClamp={1} style={{ flex: 1 }}>
                      {c.message}
                    </Text>
                    <Text size="xs" c="dimmed" style={{ whiteSpace: "nowrap" }}>
                      {c.author} · {timeAgo(c.date)}
                    </Text>
                  </Group>
                ))
              )}
            </Stack>
            <Stack gap={4}>
              <Text size="sm" fw={500}>
                Pull requests
              </Text>
              {r.open_pulls.length + r.recent_merged.length === 0 ? (
                <Text size="sm" c="dimmed">
                  None recently.
                </Text>
              ) : (
                [...r.open_pulls, ...r.recent_merged]
                  .slice(0, 10)
                  .map((p) => <PullRow key={p.number} pull={p} />)
              )}
            </Stack>
          </SimpleGrid>
        )}
      </Stack>
    </Card>
  );
}

function PullRow({ pull: p }: { pull: PullInfo }) {
  const color = p.state === "merged" ? "grape" : p.draft ? "gray" : "teal";
  return (
    <Group gap={6} wrap="nowrap">
      <Badge size="xs" variant="light" color={color} w={58}>
        {p.draft && p.state === "open" ? "draft" : p.state}
      </Badge>
      <Anchor
        href={p.url}
        target="_blank"
        rel="noopener noreferrer"
        size="sm"
        lineClamp={1}
        style={{ flex: 1 }}
      >
        #{p.number} {p.title}
      </Anchor>
      <Text size="xs" c="dimmed" style={{ whiteSpace: "nowrap" }}>
        {p.author} · {timeAgo(p.updated_at)}
      </Text>
    </Group>
  );
}

const STATE_COLORS: Record<string, string> = {
  completed: "teal",
  started: "blue",
  unstarted: "gray",
  backlog: "gray",
  triage: "orange",
  canceled: "red",
};

function LinearCard({ linear: l, now }: { linear: LinearUpdates; now: number }) {
  if (l.error) {
    return (
      <Alert color="orange" icon={<IconAlertTriangle />}>
        {l.error}
      </Alert>
    );
  }
  const total = Object.values(l.counts).reduce((a, b) => a + b, 0) || 1;
  const done = l.counts.completed ?? 0;
  const doing = l.counts.started ?? 0;
  const todo = (l.counts.unstarted ?? 0) + (l.counts.backlog ?? 0) + (l.counts.triage ?? 0);
  const weekAgo = now - 7 * 86400 * 1000;
  const doneThisWeek = l.issues.filter(
    (i) => i.completed_at && new Date(i.completed_at).getTime() > weekAgo,
  ).length;
  return (
    <Card withBorder>
      <Stack gap="sm">
        <Group justify="space-between">
          <Anchor href={l.url ?? undefined} target="_blank" rel="noopener noreferrer" fw={600}>
            {l.name} {l.key ? `(${l.key})` : ""}
          </Anchor>
          <Group gap={6}>
            <Badge variant="light" color="teal">
              {doneThisWeek} done this week
            </Badge>
            <Badge variant="light" color="blue">
              {doing} in progress
            </Badge>
            <Badge variant="light" color="gray">
              {todo} to do
            </Badge>
          </Group>
        </Group>
        <Tooltip
          label={`Of the ${total} most recently updated issues: ${done} done, ${doing} in progress, ${todo} to do`}
        >
          <Progress.Root size="lg">
            <Progress.Section value={(done / total) * 100} color="teal" />
            <Progress.Section value={(doing / total) * 100} color="blue" />
            <Progress.Section value={(todo / total) * 100} color="gray" />
          </Progress.Root>
        </Tooltip>
        <Table fz="sm" verticalSpacing={4}>
          <Table.Tbody>
            {l.issues.slice(0, 15).map((i) => (
              <Table.Tr key={i.identifier}>
                <Table.Td w={90}>
                  <Anchor
                    href={i.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    size="xs"
                    ff="monospace"
                  >
                    {i.identifier}
                  </Anchor>
                </Table.Td>
                <Table.Td>
                  <Text size="sm" lineClamp={1}>
                    {i.title}
                  </Text>
                </Table.Td>
                <Table.Td w={130}>
                  <Badge size="xs" variant="light" color={STATE_COLORS[i.state_type] ?? "gray"}>
                    {i.state}
                  </Badge>
                </Table.Td>
                <Table.Td w={160}>
                  <Text size="xs" c="dimmed">
                    {i.assignee ?? "unassigned"} · {timeAgo(i.updated_at)}
                  </Text>
                </Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      </Stack>
    </Card>
  );
}
