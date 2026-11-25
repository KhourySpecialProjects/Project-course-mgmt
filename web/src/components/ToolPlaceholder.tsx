"use client";

import { Card, List, Stack, Text, Title } from "@mantine/core";

import { ToolKeys } from "@/components/ToolKeys";
import { ToolStatusAlert } from "@/components/ToolStatusAlert";

interface Props {
  toolId: string;
  title: string;
  intro: string;
  planned: string[];
}

/** A simple page for a tool that hasn't been built yet. */
export function ToolPlaceholder({ toolId, title, intro, planned }: Props) {
  return (
    <Stack gap="lg" maw={720}>
      <div>
        <Title order={2}>{title}</Title>
        <Text c="dimmed">{intro}</Text>
      </div>
      <ToolStatusAlert toolId={toolId} />
      <ToolKeys toolId={toolId} />
      <Card withBorder>
        <Title order={5} mb="xs">
          Planned features
        </Title>
        <List spacing={4} size="sm">
          {planned.map((p) => (
            <List.Item key={p}>{p}</List.Item>
          ))}
        </List>
      </Card>
    </Stack>
  );
}
