"use client";

// System settings (superusers only): every API key in one place.
//   Your API keys   - personal tokens (GitHub, Linear, ...): tools act as you.
//   Shared API keys - one value for the whole app (Anthropic, Coolify server URL, ...).
// Users who aren't superusers manage their personal keys on their Account page.

import { Alert, Stack, Text, Title } from "@mantine/core";

import { useAuth } from "@/components/AuthProvider";
import { CredentialList } from "@/components/CredentialList";

export default function SystemSettingsPage() {
  const { user } = useAuth();

  if (!user?.is_superuser) {
    return <Alert color="red">You need to be a superuser to view this page.</Alert>;
  }

  return (
    <Stack gap="xl" maw={760}>
      <div>
        <Title order={2}>System settings</Title>
        <Text c="dimmed">All of the workbench&apos;s API keys, in one place.</Text>
      </div>

      <Stack gap="sm">
        <div>
          <Title order={4}>Your API keys</Title>
          <Text size="sm" c="dimmed">
            Your personal tokens. Tools use them to act on your behalf, so actions in GitHub,
            Linear, and Coolify show up as yours. Only you can use them. Other users add their own
            on their Account page.
          </Text>
        </div>
        <CredentialList endpoint="/credentials/me" />
      </Stack>

      <Stack gap="sm">
        <div>
          <Title order={4}>Shared API keys</Title>
          <Text size="sm" c="dimmed">
            Keys and addresses the app itself uses, shared by everyone. Only superusers can change
            them.
          </Text>
        </div>
        <CredentialList endpoint="/credentials/system" emptyMessage="No shared API keys defined." />
      </Stack>
    </Stack>
  );
}
