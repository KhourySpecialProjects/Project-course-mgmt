"use client";

import { Button, Card, Group, PasswordInput, Stack, Text, Title } from "@mantine/core";
import { useForm } from "@mantine/form";
import { notifications } from "@mantine/notifications";
import { useState } from "react";

import { useAuth } from "@/components/AuthProvider";
import { api } from "@/lib/api";

const MIN_PASSWORD_LENGTH = 8; // matches api/app/core/security.py

export default function AccountPage() {
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
    <Stack gap="lg" maw={520}>
      <Title order={2}>Account</Title>

      <Card withBorder>
        <Text size="sm" c="dimmed">
          Signed in as
        </Text>
        <Text fw={600}>{user?.email}</Text>
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
