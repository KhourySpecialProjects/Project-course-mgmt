"use client";

// Account page with two tabs:
//   Profile   - who you're signed in as, and changing your password.
//   API keys  - your personal tokens for tools like GitHub and Linear.
//
// The tab is kept in the URL (/account?tab=api-keys) so other pages can link
// straight to it.

import { Button, Card, Group, PasswordInput, Stack, Tabs, Text, Title } from "@mantine/core";
import { useForm } from "@mantine/form";
import { notifications } from "@mantine/notifications";
import { IconKey, IconUser } from "@tabler/icons-react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";

import { useAuth } from "@/components/AuthProvider";
import { CredentialList } from "@/components/CredentialList";
import { api } from "@/lib/api";

const MIN_PASSWORD_LENGTH = 8; // matches api/app/core/security.py

export default function AccountPage() {
  // useSearchParams() must be inside a <Suspense> boundary.
  return (
    <Suspense>
      <AccountTabs />
    </Suspense>
  );
}

function AccountTabs() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const tab = searchParams.get("tab") === "api-keys" ? "api-keys" : "profile";

  return (
    <Stack gap="lg" maw={760}>
      <Title order={2}>Account</Title>
      <Tabs
        value={tab}
        onChange={(v) => router.replace(v === "api-keys" ? `${pathname}?tab=api-keys` : pathname)}
      >
        <Tabs.List>
          <Tabs.Tab value="profile" leftSection={<IconUser size={16} />}>
            Profile
          </Tabs.Tab>
          <Tabs.Tab value="api-keys" leftSection={<IconKey size={16} />}>
            API keys
          </Tabs.Tab>
        </Tabs.List>

        <Tabs.Panel value="profile" pt="md">
          <ProfileTab />
        </Tabs.Panel>
        <Tabs.Panel value="api-keys" pt="md">
          <Stack>
            <Text size="sm" c="dimmed">
              Your personal tokens. Tools use them to act on your behalf, so actions in GitHub and
              Linear show up as yours. Only you can use them; administrators can&apos;t see them.
            </Text>
            <CredentialList endpoint="/credentials/me" />
          </Stack>
        </Tabs.Panel>
      </Tabs>
    </Stack>
  );
}

function ProfileTab() {
  const { user } = useAuth();
  const [saving, setSaving] = useState(false);

  const form = useForm({
    initialValues: { current_password: "", new_password: "", confirm: "" },
    validate: {
      current_password: (v) => (v ? null : "Required"),
      new_password: (v) =>
        v.length >= MIN_PASSWORD_LENGTH ? null : `At least ${MIN_PASSWORD_LENGTH} characters`,
      confirm: (v, values) => (v === values.new_password ? null : "Passwords do not match"),
    },
  });

  async function handleSubmit(values: typeof form.values) {
    setSaving(true);
    try {
      await api.post("/auth/change-password", {
        current_password: values.current_password,
        new_password: values.new_password,
      });
      form.reset();
      notifications.show({ color: "teal", message: "Password changed" });
    } catch (err) {
      notifications.show({ color: "red", message: (err as Error).message });
    } finally {
      setSaving(false);
    }
  }

  return (
    <Stack maw={520}>
      <Card withBorder>
        <Text size="sm" c="dimmed">
          Signed in as
        </Text>
        <Text fw={600}>{user?.email}</Text>
        {user?.full_name && <Text size="sm">{user.full_name}</Text>}
        {user?.is_superuser && (
          <Text size="sm" c="dimmed">
            Superuser
          </Text>
        )}
      </Card>

      <Card withBorder>
        <form onSubmit={form.onSubmit(handleSubmit)}>
          <Stack>
            <Title order={4}>Change password</Title>
            <PasswordInput
              label="Current password"
              autoComplete="current-password"
              {...form.getInputProps("current_password")}
            />
            <PasswordInput
              label="New password"
              autoComplete="new-password"
              {...form.getInputProps("new_password")}
            />
            <PasswordInput
              label="Repeat new password"
              autoComplete="new-password"
              {...form.getInputProps("confirm")}
            />
            <Group justify="flex-end">
              <Button type="submit" loading={saving}>
                Change password
              </Button>
            </Group>
          </Stack>
        </form>
      </Card>
    </Stack>
  );
}
