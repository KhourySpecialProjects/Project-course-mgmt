"use client";

// User management (superusers only). The API also enforces this; hiding the
// page is just for a nicer experience.
//
// Two tabs:
//   Users        - everyone with an account; switch accounts on/off and grant admin.
//   Invitations  - one-time invite links, with their status.

import {
  ActionIcon,
  Alert,
  Badge,
  Button,
  Checkbox,
  Group,
  Menu,
  Modal,
  Stack,
  Switch,
  Table,
  Tabs,
  Text,
  TextInput,
  Title,
} from "@mantine/core";
import { useForm } from "@mantine/form";
import { notifications } from "@mantine/notifications";
import { IconBan, IconDots, IconLink, IconMailPlus, IconUsers } from "@tabler/icons-react";
import { useEffect, useState } from "react";

import { useAuth } from "@/components/AuthProvider";
import { InviteLink } from "@/components/InviteLink";
import { api } from "@/lib/api";
import { formatDate } from "@/lib/format";
import type { Invite, InviteCreated, InviteStatus, User } from "@/lib/types";

type Tab = "users" | "invitations";

export default function UsersPage() {
  const { user: me } = useAuth();
  const [tab, setTab] = useState<Tab>("users");
  const [inviteFormOpen, setInviteFormOpen] = useState(false);
  // Set right after an invite is created, so its one-time link can be shown.
  const [created, setCreated] = useState<InviteCreated | null>(null);
  // Bump to make the invitations list reload.
  const [invitesVersion, setInvitesVersion] = useState(0);

  if (!me?.is_superuser) {
    return <Alert color="red">You need to be a superuser to view this page.</Alert>;
  }

  function handleCreated(invite: InviteCreated) {
    setInviteFormOpen(false);
    setCreated(invite);
    setTab("invitations");
    setInvitesVersion((v) => v + 1);
  }

  return (
    <Stack gap="lg">
      <Group justify="space-between">
        <Title order={2}>Users</Title>
        <Button leftSection={<IconMailPlus size={16} />} onClick={() => setInviteFormOpen(true)}>
          Invite user
        </Button>
      </Group>

      <Tabs value={tab} onChange={(v) => setTab((v as Tab) ?? "users")}>
        <Tabs.List>
          <Tabs.Tab value="users" leftSection={<IconUsers size={16} />}>
            Users
          </Tabs.Tab>
          <Tabs.Tab value="invitations" leftSection={<IconMailPlus size={16} />}>
            Invitations
          </Tabs.Tab>
        </Tabs.List>

        <Tabs.Panel value="users" pt="md">
          <UsersTable me={me} />
        </Tabs.Panel>
        <Tabs.Panel value="invitations" pt="md">
          <InvitationsTable version={invitesVersion} onNewLink={handleCreated} />
        </Tabs.Panel>
      </Tabs>

      <Modal opened={inviteFormOpen} onClose={() => setInviteFormOpen(false)} title="Invite user">
        <InviteForm onCreated={handleCreated} />
      </Modal>

      <Modal
        opened={created !== null}
        onClose={() => setCreated(null)}
        title="Invite link ready"
        size="lg"
        // Don't let a stray click outside dismiss the only chance to copy the link.
        closeOnClickOutside={false}
      >
        {created && <InviteLink invite={created} onDone={() => setCreated(null)} />}
      </Modal>
    </Stack>
  );
}

// --- Users tab --------------------------------------------------------------

function UsersTable({ me }: { me: User }) {
  const [users, setUsers] = useState<User[]>([]);

  useEffect(() => {
    api
      .get<User[]>("/users")
      .then(setUsers)
      .catch((err: Error) => notifications.show({ color: "red", message: err.message }));
  }, []);

  async function update(user: User, changes: Partial<User>) {
    try {
      const updated = await api.patch<User>(`/users/${user.id}`, changes);
      setUsers((list) => list.map((u) => (u.id === updated.id ? updated : u)));
    } catch (err) {
      notifications.show({ color: "red", message: (err as Error).message });
    }
  }

  return (
    <Table.ScrollContainer minWidth={600}>
      <Table striped highlightOnHover verticalSpacing="sm">
        <Table.Thead>
          <Table.Tr>
            <Table.Th>Email</Table.Th>
            <Table.Th>Name</Table.Th>
            <Table.Th>Active</Table.Th>
            <Table.Th>Superuser</Table.Th>
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {users.map((u) => {
            const isMe = u.id === me.id;
            return (
              <Table.Tr key={u.id}>
                <Table.Td>
                  <Group gap="xs">
                    <Text size="sm">{u.email}</Text>
                    {isMe && <Badge size="xs">you</Badge>}
                  </Group>
                </Table.Td>
                <Table.Td>{u.full_name}</Table.Td>
                <Table.Td>
                  <Switch
                    aria-label={`Active: ${u.email}`}
                    checked={u.is_active}
                    disabled={isMe}
                    onChange={(e) => update(u, { is_active: e.currentTarget.checked })}
                  />
                </Table.Td>
                <Table.Td>
                  <Switch
                    aria-label={`Superuser: ${u.email}`}
                    checked={u.is_superuser}
                    disabled={isMe}
                    onChange={(e) => update(u, { is_superuser: e.currentTarget.checked })}
                  />
                </Table.Td>
              </Table.Tr>
            );
          })}
        </Table.Tbody>
      </Table>
    </Table.ScrollContainer>
  );
}

// --- Invitations tab --------------------------------------------------------

const STATUS_COLORS: Record<InviteStatus, string> = {
  pending: "blue",
  accepted: "teal",
  expired: "gray",
  revoked: "red",
};

function InvitationsTable({
  version,
  onNewLink,
}: {
  version: number;
  onNewLink: (invite: InviteCreated) => void;
}) {
  const [invites, setInvites] = useState<Invite[] | null>(null);

  useEffect(() => {
    api
      .get<Invite[]>("/invites")
      .then(setInvites)
      .catch((err: Error) => notifications.show({ color: "red", message: err.message }));
  }, [version]);

  async function revoke(invite: Invite) {
    try {
      const updated = await api.post<Invite>(`/invites/${invite.id}/revoke`);
      setInvites((list) => list?.map((i) => (i.id === updated.id ? updated : i)) ?? null);
      notifications.show({ message: `Invite for ${invite.email} revoked` });
    } catch (err) {
      notifications.show({ color: "red", message: (err as Error).message });
    }
  }

  // "New link" re-invites with the same details. The server revokes any
  // still-pending link for that email, so only the newest one works.
  async function newLink(invite: Invite) {
    try {
      onNewLink(
        await api.post<InviteCreated>("/invites", {
          email: invite.email,
          full_name: invite.full_name,
          is_superuser: invite.is_superuser,
        }),
      );
    } catch (err) {
      notifications.show({ color: "red", message: (err as Error).message });
    }
  }

  if (invites === null) return null;
  if (invites.length === 0) {
    return (
      <Text c="dimmed" ta="center" py="xl">
        No invitations yet. Use <b>Invite user</b> to create a one-time sign-up link.
      </Text>
    );
  }

  return (
    <Table.ScrollContainer minWidth={700}>
      <Table highlightOnHover verticalSpacing="sm">
        <Table.Thead>
          <Table.Tr>
            <Table.Th>Email</Table.Th>
            <Table.Th>Role</Table.Th>
            <Table.Th>Status</Table.Th>
            <Table.Th>Invited</Table.Th>
            <Table.Th>Expires</Table.Th>
            <Table.Th />
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {invites.map((i) => (
            <Table.Tr key={i.id}>
              <Table.Td>
                <Text size="sm">{i.email}</Text>
                {i.full_name && (
                  <Text size="xs" c="dimmed">
                    {i.full_name}
                  </Text>
                )}
              </Table.Td>
              <Table.Td>
                <Text size="sm">{i.is_superuser ? "Superuser" : "User"}</Text>
              </Table.Td>
              <Table.Td>
                <Badge color={STATUS_COLORS[i.status]} variant="light">
                  {i.status}
                </Badge>
              </Table.Td>
              <Table.Td>
                <Text size="sm">{formatDate(i.created_at)}</Text>
                {i.created_by_email && (
                  <Text size="xs" c="dimmed">
                    by {i.created_by_email}
                  </Text>
                )}
              </Table.Td>
              <Table.Td>
                <Text size="sm">
                  {i.status === "accepted" && i.accepted_at
                    ? `Joined ${formatDate(i.accepted_at)}`
                    : i.status === "revoked"
                      ? "—"
                      : formatDate(i.expires_at)}
                </Text>
              </Table.Td>
              <Table.Td>
                {i.status !== "accepted" && (
                  <Menu position="bottom-end" withinPortal>
                    <Menu.Target>
                      <ActionIcon
                        variant="subtle"
                        color="gray"
                        aria-label={`Actions for ${i.email}`}
                      >
                        <IconDots size={16} />
                      </ActionIcon>
                    </Menu.Target>
                    <Menu.Dropdown>
                      <Menu.Item leftSection={<IconLink size={14} />} onClick={() => newLink(i)}>
                        New link
                      </Menu.Item>
                      {i.status === "pending" && (
                        <Menu.Item
                          color="red"
                          leftSection={<IconBan size={14} />}
                          onClick={() => revoke(i)}
                        >
                          Revoke
                        </Menu.Item>
                      )}
                    </Menu.Dropdown>
                  </Menu>
                )}
              </Table.Td>
            </Table.Tr>
          ))}
        </Table.Tbody>
      </Table>
    </Table.ScrollContainer>
  );
}

// --- Invite form ------------------------------------------------------------

function InviteForm({ onCreated }: { onCreated: (invite: InviteCreated) => void }) {
  const [saving, setSaving] = useState(false);
  const form = useForm({
    initialValues: { email: "", full_name: "", is_superuser: false },
    validate: {
      email: (v) => (/^\S+@\S+\.\S+$/.test(v) ? null : "Enter a valid email"),
    },
  });

  async function handleSubmit(values: typeof form.values) {
    setSaving(true);
    try {
      onCreated(await api.post<InviteCreated>("/invites", values));
    } catch (err) {
      notifications.show({ color: "red", message: (err as Error).message });
    } finally {
      setSaving(false);
    }
  }

  return (
    <form onSubmit={form.onSubmit(handleSubmit)}>
      <Stack>
        <Text size="sm" c="dimmed">
          You&apos;ll get a one-time link to send to this person. They choose their own password
          when they open it.
        </Text>
        <TextInput
          label="Email"
          type="email"
          required
          data-autofocus
          {...form.getInputProps("email")}
        />
        <TextInput
          label="Full name"
          description="Optional. They can change it when accepting."
          {...form.getInputProps("full_name")}
        />
        <Checkbox
          label="Superuser (can manage users and system settings)"
          {...form.getInputProps("is_superuser", { type: "checkbox" })}
        />
        <Group justify="flex-end">
          <Button type="submit" loading={saving}>
            Create invite link
          </Button>
        </Group>
      </Stack>
    </form>
  );
}
