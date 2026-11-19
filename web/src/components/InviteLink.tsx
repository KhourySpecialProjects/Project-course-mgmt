"use client";

// Shows a freshly created invite link with Copy and "Open in email" buttons.
// The link is only available right after creating the invite; the server
// keeps just a hash of it.

import {
  ActionIcon,
  Alert,
  Button,
  CopyButton,
  Group,
  Stack,
  Text,
  TextInput,
  Tooltip,
} from "@mantine/core";
import { IconCheck, IconCopy, IconInfoCircle, IconMail } from "@tabler/icons-react";

import { formatDateTime } from "@/lib/format";
import type { InviteCreated } from "@/lib/types";

/** Build the full link from the token, using the address this app is served from. */
export function inviteUrl(token: string): string {
  return `${window.location.origin}/invite/${token}`;
}

export function InviteLink({ invite, onDone }: { invite: InviteCreated; onDone: () => void }) {
  const url = inviteUrl(invite.token);
  const greeting = invite.full_name ? `Hi ${invite.full_name},` : "Hi,";
  const mailto =
    `mailto:${encodeURIComponent(invite.email)}` +
    `?subject=${encodeURIComponent("Your Course Workbench account")}` +
    `&body=${encodeURIComponent(
      `${greeting}\n\nYou've been invited to the Course Workbench. ` +
        `Open this link to set your password and sign in:\n\n${url}\n\n` +
        `The link works once and expires on ${formatDateTime(invite.expires_at)}.`,
    )}`;

  return (
    <Stack>
      <Text size="sm">
        Send this link to <b>{invite.email}</b>. They&apos;ll choose a password and be signed in.
      </Text>

      <TextInput
        value={url}
        readOnly
        aria-label="Invite link"
        onFocus={(e) => e.currentTarget.select()}
        rightSection={
          <CopyButton value={url} timeout={2000}>
            {({ copied, copy }) => (
              <Tooltip label={copied ? "Copied" : "Copy"} withArrow>
                <ActionIcon
                  variant="subtle"
                  color={copied ? "teal" : "gray"}
                  onClick={copy}
                  aria-label="Copy link"
                >
                  {copied ? <IconCheck size={16} /> : <IconCopy size={16} />}
                </ActionIcon>
              </Tooltip>
            )}
          </CopyButton>
        }
      />

      <Alert variant="light" icon={<IconInfoCircle />} p="sm">
        The link works once and expires {formatDateTime(invite.expires_at)}. For security it
        won&apos;t be shown again. If it&apos;s lost, use <b>New link</b> on the Invitations tab.
      </Alert>

      <Group justify="space-between">
        <Button component="a" href={mailto} variant="default" leftSection={<IconMail size={16} />}>
          Open in email
        </Button>
        <Group gap="xs">
          <CopyButton value={url} timeout={2000}>
            {({ copied, copy }) => (
              <Button
                variant="light"
                color={copied ? "teal" : undefined}
                onClick={copy}
                leftSection={copied ? <IconCheck size={16} /> : <IconCopy size={16} />}
              >
                {copied ? "Copied" : "Copy link"}
              </Button>
            )}
          </CopyButton>
          <Button onClick={onDone}>Done</Button>
        </Group>
      </Group>
    </Stack>
  );
}
