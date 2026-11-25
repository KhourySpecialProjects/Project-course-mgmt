"use client";

// One team, all in one place: its students, links, and status (Overview), its
// recent GitHub and Linear work (Updates), and its Coolify (Coolify).

import {
  Alert,
  Anchor,
  Button,
  Card,
  Group,
  Skeleton,
  Stack,
  Tabs,
  Text,
  Title,
} from "@mantine/core";
import {
  IconActivity,
  IconArrowLeft,
  IconExternalLink,
  IconRocket,
  IconUsers,
} from "@tabler/icons-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { TeamStatusLine } from "@/components/teams/TeamCard";
import { TeamMembers } from "@/components/teams/TeamMembers";
import { TeamUpdates } from "@/components/teams/TeamUpdates";
import { api } from "@/lib/api";
import type { CourseSummary, Team } from "@/lib/types";
import { CoolifyTeamPanel } from "@/modules/coolify/CoolifyTeamPanel";
import { ToolIcon } from "@/modules/registry";

type Tab = "overview" | "updates" | "coolify";

export function TeamPage({ teamId }: { teamId: number }) {
  const [team, setTeam] = useState<Team | null | undefined>(null);
  const [summary, setSummary] = useState<CourseSummary | null>(null);
  const [tab, setTab] = useState<Tab>("overview");

  useEffect(() => {
    api
      .get<Team[]>("/teams")
      .then((all) => setTeam(all.find((t) => t.id === teamId)))
      .catch(() => setTeam(undefined));
    api
      .get<CourseSummary>("/tools/coolify/summary")
      .then(setSummary)
      .catch(() => setSummary(null));
  }, [teamId]);

  if (team === null) return <Skeleton h={300} />;
  if (team === undefined) {
    return (
      <Alert color="red" title="Team not found">
        <Anchor component={Link} href="/">
          Back to the dashboard
        </Anchor>
      </Alert>
    );
  }

  const teamSummary = summary?.teams.find((t) => t.team_id === team.id);

  return (
    <Stack gap="lg">
      <div>
        <Anchor component={Link} href="/" size="sm" c="dimmed">
          <Group gap={4}>
            <IconArrowLeft size={14} /> Dashboard
          </Group>
        </Anchor>
        <Title order={2}>{team.name}</Title>
        <Text c="dimmed" size="sm">
          {team.members.length} student{team.members.length === 1 ? "" : "s"}
        </Text>
      </div>

      <Tabs value={tab} onChange={(v) => setTab((v as Tab) ?? "overview")}>
        <Tabs.List>
          <Tabs.Tab value="overview" leftSection={<IconUsers size={16} />}>
            Overview
          </Tabs.Tab>
          <Tabs.Tab value="updates" leftSection={<IconActivity size={16} />}>
            Updates
          </Tabs.Tab>
          <Tabs.Tab value="coolify" leftSection={<IconRocket size={16} />}>
            Coolify
          </Tabs.Tab>
        </Tabs.List>

        <Tabs.Panel value="overview" pt="md">
          <Stack gap="md">
            <Card withBorder>
              <Stack gap="xs">
                <Text fw={600}>Links</Text>
                {team.links.length === 0 ? (
                  <Text size="sm" c="dimmed">
                    No links yet: set them up from the team&apos;s card on the dashboard.
                  </Text>
                ) : (
                  <Group gap="xs">
                    {team.links.map((l) => (
                      <Button
                        key={l.id}
                        component="a"
                        href={l.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        size="xs"
                        variant="light"
                        color={l.service_id ? undefined : "gray"}
                        leftSection={<ToolIcon toolId={l.service_id} size={14} />}
                        rightSection={<IconExternalLink size={12} />}
                        title={l.label}
                      >
                        {l.service_id
                          ? l.service_id[0].toUpperCase() + l.service_id.slice(1)
                          : l.label}
                      </Button>
                    ))}
                  </Group>
                )}
                {teamSummary && <TeamStatusLine team={team} summary={teamSummary} />}
              </Stack>
            </Card>
            <Card withBorder>
              <TeamMembers team={team} onChange={setTeam} />
            </Card>
          </Stack>
        </Tabs.Panel>

        <Tabs.Panel value="updates" pt="md">
          {tab === "updates" && <TeamUpdates teamId={team.id} embedded />}
        </Tabs.Panel>

        <Tabs.Panel value="coolify" pt="md">
          {tab === "coolify" && <CoolifyTeamPanel teamId={team.id} embedded />}
        </Tabs.Panel>
      </Tabs>
    </Stack>
  );
}
