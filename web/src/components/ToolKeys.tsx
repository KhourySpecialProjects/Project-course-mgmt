"use client";

// A tool's own API keys, on its page: add, replace, or remove each one without
// going to System settings. Personal keys for everyone; the shared ones (like the
// GitHub organization) for superusers, who are the only ones who can change them.

import { Card, Skeleton, Stack, Text, Title } from "@mantine/core";
import { useEffect, useState } from "react";

import { useAuth } from "@/components/AuthProvider";
import { CredentialList } from "@/components/CredentialList";
import { api } from "@/lib/api";
import type { ToolStatus } from "@/lib/types";

export function ToolKeys({ toolId }: { toolId: string }) {
  const { user } = useAuth();
  const [status, setStatus] = useState<ToolStatus | null>(null);

  useEffect(() => {
    api
      .get<ToolStatus>(`/tools/${toolId}/status`)
      .then(setStatus)
      .catch(() => setStatus(null));
  }, [toolId]);

  if (!status) return <Skeleton h={80} />;
  const mine = status.credentials.filter((c) => c.scope === "user").map((c) => c.key);
  const shared = status.credentials.filter((c) => c.scope === "system").map((c) => c.key);
  if (mine.length === 0 && shared.length === 0) return null;

  return (
    <Card withBorder id="api-keys">
      <Stack gap="md">
        <div>
          <Title order={5}>API keys</Title>
          <Text size="sm" c="dimmed">
            The keys this tool uses. Replace one any time, e.g. with a new token or one from a
            different account. Saved keys are never shown again.
          </Text>
        </div>
        {mine.length > 0 && (
          <Stack gap="xs">
            <Text size="sm" fw={500}>
              Yours
            </Text>
            <CredentialList endpoint="/credentials/me" keys={mine} />
          </Stack>
        )}
        {shared.length > 0 &&
          (user?.is_superuser ? (
            <Stack gap="xs">
              <Text size="sm" fw={500}>
                Shared by everyone
              </Text>
              <CredentialList endpoint="/credentials/system" keys={shared} />
            </Stack>
          ) : (
            <Text size="xs" c="dimmed">
              Shared settings (
              {status.credentials
                .filter((c) => c.scope === "system")
                .map((c) => c.label)
                .join(", ")}
              ) are managed by an administrator.
            </Text>
          ))}
      </Stack>
    </Card>
  );
}
