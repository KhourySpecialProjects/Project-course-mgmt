"use client";

// Public page for accepting an invite: /invite/<token>
//
// The [token] folder name makes this a *dynamic route*: whatever comes after
// /invite/ in the URL is available as params.token.

import { Alert, Anchor, Button, PasswordInput, Stack, Text, TextInput } from "@mantine/core";
import { useForm } from "@mantine/form";
import { IconAlertCircle, IconInfoCircle } from "@tabler/icons-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { AuthCard } from "@/components/AuthCard";
import { useAuth } from "@/components/AuthProvider";
import { FullPageLoader } from "@/components/FullPageLoader";
import { api } from "@/lib/api";
import { formatDateTime } from "@/lib/format";
import type { InvitePreview } from "@/lib/types";

const MIN_PASSWORD_LENGTH = 8; // matches api/app/core/security.py

export default function AcceptInvitePage() {
  const { token } = useParams<{ token: string }>();
  const [invite, setInvite] = useState<InvitePreview | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  useEffect(() => {
    api
      .get<InvitePreview>(`/invites/accept/${encodeURIComponent(token)}`)
      .then(setInvite)
      .catch((err: Error) => setLoadError(err.message));
  }, [token]);

  if (loadError) {
    return (
      <AuthCard subtitle="Invitation">
        <Alert color="red" icon={<IconAlertCircle />} title="This link can't be used">
          {loadError} Ask the person who invited you to send a new link.
        </Alert>
        <Anchor component={Link} href="/login" size="sm" ta="center">
          Already have an account? Sign in
        </Anchor>
      </AuthCard>
    );
  }
  if (!invite) return <FullPageLoader />;

  return (
    <AuthCard subtitle="You've been invited. Choose a password to create your account.">
      <AcceptForm token={token} invite={invite} />
    </AuthCard>
  );
}

function AcceptForm({ token, invite }: { token: string; invite: InvitePreview }) {
  const { user, refresh } = useAuth();
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const form = useForm({
    initialValues: { full_name: invite.full_name, password: "", confirm: "" },
    validate: {
      password: (v) =>
        v.length >= MIN_PASSWORD_LENGTH ? null : `At least ${MIN_PASSWORD_LENGTH} characters`,
      confirm: (v, values) => (v === values.password ? null : "Passwords do not match"),
    },
  });

  async function handleSubmit(values: typeof form.values) {
    setError(null);
    setSubmitting(true);
    try {
      // On success the API also signs us in (sets the session cookie).
      await api.post(`/invites/accept/${encodeURIComponent(token)}`, {
        full_name: values.full_name,
        password: values.password,
      });
      await refresh();
      router.replace("/");
    } catch (err) {
      setError((err as Error).message);
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={form.onSubmit(handleSubmit)}>
      <Stack>
        {user && (
          <Alert color="yellow" icon={<IconInfoCircle />} p="sm">
            You&apos;re currently signed in as {user.email}. Creating this account will sign you in
            as {invite.email} instead.
          </Alert>
        )}
        {error && (
          <Alert color="red" icon={<IconAlertCircle />}>
            {error}
          </Alert>
        )}

        <TextInput label="Email" value={invite.email} readOnly disabled />
        <TextInput label="Full name" autoComplete="name" {...form.getInputProps("full_name")} />
        <PasswordInput
          label="Password"
          description={`At least ${MIN_PASSWORD_LENGTH} characters`}
          autoComplete="new-password"
          required
          {...form.getInputProps("password")}
        />
        <PasswordInput
          label="Repeat password"
          autoComplete="new-password"
          required
          {...form.getInputProps("confirm")}
        />
        <Button type="submit" loading={submitting} fullWidth mt="sm">
          Create account
        </Button>
        <Text size="xs" c="dimmed" ta="center">
          This link expires {formatDateTime(invite.expires_at)}.
        </Text>
      </Stack>
    </form>
  );
}
