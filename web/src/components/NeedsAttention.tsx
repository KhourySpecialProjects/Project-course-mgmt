"use client";

// The dashboard's "Needs attention": what's broken or urgent across every team,
// most urgent first (apps that are down, security updates, servers waiting for
// updates or a reboot, teams not connected). Each item opens the team's panel.

import { Anchor, Badge, Card, Group, Skeleton, Stack, Text, Title } from "@mantine/core";
import { IconCircleCheck } from "@tabler/icons-react";
import Link from "next/link";
import { useState } from "react";

import { timeAgo } from "@/lib/format";
import type { CourseSummary } from "@/lib/types";
import { attentionItems } from "@/modules/coolify/health";

const SHOWN = 8;
const COLORS = { red: "red", orange: "orange", gray: "gray" } as const;
const LABELS = { red: "Urgent", orange: "Check", gray: "Setup" } as const;

export function NeedsAttention({ summary }: { summary: CourseSummary | null | undefined }) {
  const [showAll, setShowAll] = useState(false);
  if (summary === undefined) return null; // Coolify isn't set up: nothing to say yet
  if (summary === null) return <Skeleton h={90} />;

  const items = attentionItems(summary);
  const shown = showAll ? items : items.slice(0, SHOWN);

  return (
    <Card withBorder>
      <Stack gap="xs">
        <Group justify="space-between">
          <Title order={4}>Needs attention</Title>
          <Text size="xs" c="dimmed">
            Coolify, checked {timeAgo(summary.generated_at)} ·{" "}
            <Anchor component={Link} href="/tools/coolify" size="xs">
              Security page
            </Anchor>
          </Text>
        </Group>
        {items.length === 0 ? (
          <Group gap="xs">
            <IconCircleCheck size={18} color="var(--mantine-color-teal-6)" />
            <Text size="sm">
              All teams&apos; apps are running, with no urgent security updates.
            </Text>
          </Group>
        ) : (
          <>
            {shown.map((item, i) => (
              <Group key={`${item.teamId}-${i}`} gap="xs" wrap="nowrap">
                <Badge
                  color={COLORS[item.level]}
                  variant="light"
                  miw={78}
                  style={{ flexShrink: 0 }}
                >
                  {LABELS[item.level]}
                </Badge>
                <Anchor component={Link} href={`/teams/${item.teamId}/coolify`} size="sm" fw={500}>
                  {item.teamName}
                </Anchor>
                <Text size="sm" lineClamp={1}>
                  {item.text}
                </Text>
              </Group>
            ))}
            {items.length > SHOWN && (
              <Anchor component="button" size="sm" onClick={() => setShowAll((v) => !v)}>
                {showAll ? "Show less" : `Show all ${items.length}`}
              </Anchor>
            )}
          </>
        )}
      </Stack>
    </Card>
  );
}
