"use client";

// Dashboard: the first page after logging in.

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
import { api } from "@/lib/api";
import type { ToolInfo } from "@/lib/types";
import { toolModules } from "@/modules/registry";

export default function DashboardPage() {
  const { user } = useAuth();
  const [tools, setTools] = useState<ToolInfo[] | null>(null);

  useEffect(() => {
    api
      .get<ToolInfo[]>("/tools")
      .then(setTools)
      .catch(() => setTools([]));
  }, []);

  return (
    <Stack gap="lg">
      <div>
        <Title order={2}>Welcome{user?.full_name ? `, ${user.full_name}` : ""}</Title>
        <Text c="dimmed">Pick a tool to get started.</Text>
      </div>

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
  );
}
