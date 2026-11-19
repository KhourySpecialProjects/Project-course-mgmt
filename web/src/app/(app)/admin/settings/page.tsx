"use client";

// System-wide settings (superusers only). Currently: API keys shared by the
// whole app, such as the Anthropic API key. Personal keys live on each
// user's Account page instead.

import { Alert, Stack, Text, Title } from "@mantine/core";

import { useAuth } from "@/components/AuthProvider";
import { CredentialList } from "@/components/CredentialList";

export default function SystemSettingsPage() {
  const { user } = useAuth();

  if (!user?.is_superuser) {
    return <Alert color="red">You need to be a superuser to view this page.</Alert>;
  }

  return (
    <Stack gap="lg" maw={760}>
      <div>
        <Title order={2}>System settings</Title>
        <Text c="dimmed">Settings that apply to everyone using the workbench.</Text>
      </div>

      <Stack gap="xs">
        <Title order={4}>System API keys</Title>
        <Text size="sm" c="dimmed">
          Keys the app itself uses, shared by all users. Personal tokens (like each
          instructor&apos;s GitHub token) are managed by each user on their Account page.
        </Text>
      </Stack>
      <CredentialList endpoint="/credentials/system" emptyMessage="No system API keys defined." />
    </Stack>
  );
}
