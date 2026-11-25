"use client";

// Dashboard: the first page after logging in. What needs attention across all
// teams, then the student teams (see components/teams/TeamsSection.tsx), then the
// tools.

import {
  Badge,
  Card,
  Group,
  SimpleGrid,
  Skeleton,
  Stack,
  Text,
  ThemeIcon,
  Title,
} from "@mantine/core";
import Link from "next/link";
import { useEffect, useState } from "react";

import { useAuth } from "@/components/AuthProvider";
import { NeedsAttention } from "@/components/NeedsAttention";
import { TeamsSection } from "@/components/teams/TeamsSection";
import { api } from "@/lib/api";
import type { CourseSummary, ToolInfo } from "@/lib/types";
import { toolModules } from "@/modules/registry";

export default function DashboardPage() {
  const { user } = useAuth();
  const [tools, setTools] = useState<ToolInfo[] | null>(null);
  // null while loading; undefined if Coolify can't be read at all.
  const [summary, setSummary] = useState<CourseSummary | null | undefined>(null);
  const [summaryVersion, setSummaryVersion] = useState(0);

  useEffect(() => {
    api
      .get<ToolInfo[]>("/tools")
      .then(setTools)
      .catch(() => setTools([]));
  }, []);

  useEffect(() => {
    api
      .get<CourseSummary>(`/tools/coolify/summary${summaryVersion ? "?refresh=true" : ""}`)
      .then(setSummary)
      .catch(() => setSummary(undefined));
  }, [summaryVersion]);

  return (
    <Stack gap="lg">
      <div>
        <Title order={2}>Welcome{user?.full_name ? `, ${user.full_name}` : ""}</Title>
        <Text c="dimmed">Here&apos;s what needs attention across your teams.</Text>
      </div>

      <NeedsAttention summary={summary} />

      <TeamsSection
        summary={summary ?? undefined}
        onTeamsChanged={() => setSummaryVersion((v) => v + 1)}
      />

      <Stack gap="sm">
        <Title order={3}>Tools</Title>
        <SimpleGrid cols={{ base: 1, sm: 2, lg: 3 }}>
          {tools === null
            ? toolModules.map((m) => <Skeleton key={m.id} h={140} />)
            : toolModules.map((m) => {
                const info = tools.find((t) => t.id === m.id);
                const Icon = m.icon;
                return (
                  <Card
                    key={m.id}
                    component={Link}
                    href={m.href}
                    withBorder
                    padding="lg"
                    style={{ textDecoration: "none" }}
                  >
                    <Group justify="space-between" mb="sm">
                      <ThemeIcon variant="light" size="xl">
                        <Icon size={24} stroke={1.5} />
                      </ThemeIcon>
                      {info && (
                        <Badge color={info.configured ? "teal" : "gray"} variant="light">
                          {info.configured ? "Configured" : "Not configured"}
                        </Badge>
                      )}
                    </Group>
                    <Text fw={600}>{m.name}</Text>
                    <Text size="sm" c="dimmed">
                      {info?.description}
                    </Text>
                  </Card>
                );
              })}
        </SimpleGrid>
      </Stack>
    </Stack>
  );
}
