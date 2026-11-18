"use client";

// User management (superusers only). The API also enforces this; hiding the
// page is just for a nicer experience.

import {
  Alert,
  Badge,
  Button,
  Checkbox,
  Group,
  Modal,
  PasswordInput,
  Stack,
  Switch,
  Table,
  Text,
  TextInput,
  Title,
} from "@mantine/core";
import { useForm } from "@mantine/form";
import { useDisclosure } from "@mantine/hooks";
import { notifications } from "@mantine/notifications";
import { IconPlus } from "@tabler/icons-react";
import { useEffect, useState } from "react";

import { useAuth } from "@/components/AuthProvider";
import { api } from "@/lib/api";
import type { User } from "@/lib/types";

export default function UsersPage() {
  const { user: me } = useAuth();
  const [users, setUsers] = useState<User[]>([]);
  const [opened, { open, close }] = useDisclosure(false);
  // Bump this number to make the effect below fetch the list again.
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    api
      .get<User[]>("/users")
      .then(setUsers)
      .catch((err: Error) => notifications.show({ color: "red", message: err.message }));
  }, [reloadKey]);

  async function update(user: User, changes: Partial<User>) {
    try {
      const updated = await api.patch<User>(`/users/${user.id}`, changes);
      setUsers((list) => list.map((u) => (u.id === updated.id ? updated : u)));
    } catch (err) {
      notifications.show({ color: "red", message: (err as Error).message });
    }
  }

  if (!me?.is_superuser) {
    return <Alert color="red">You need to be a superuser to view this page.</Alert>;
  }

  return (
    <Stack gap="lg">
      <Group justify="space-between">
        <Title order={2}>Users</Title>
        <Button leftSection={<IconPlus size={16} />} onClick={open}>
          Add user
        </Button>
      </Group>

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
                      aria-label="Active"
                      checked={u.is_active}
                      disabled={isMe}
                      onChange={(e) => update(u, { is_active: e.currentTarget.checked })}
                    />
                  </Table.Td>
                  <Table.Td>
                    <Switch
                      aria-label="Superuser"
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

      <Modal opened={opened} onClose={close} title="Add user">
        <CreateUserForm
          onCreated={() => {
            close();
            setReloadKey((k) => k + 1);
          }}
        />
      </Modal>
    </Stack>
  );
}

function CreateUserForm({ onCreated }: { onCreated: () => void }) {
  const [saving, setSaving] = useState(false);
  const form = useForm({
    initialValues: { email: "", full_name: "", password: "", is_superuser: false },
    validate: {
      email: (v) => (/^\S+@\S+$/.test(v) ? null : "Enter a valid email"),
      password: (v) => (v.length >= 8 ? null : "At least 8 characters"),
    },
  });

  async function handleSubmit(values: typeof form.values) {
    setSaving(true);
    try {
      await api.post("/users", values);
      notifications.show({ color: "teal", message: `Created ${values.email}` });
      onCreated();
    } catch (err) {
      notifications.show({ color: "red", message: (err as Error).message });
    } finally {
      setSaving(false);
    }
  }

  return (
    <form onSubmit={form.onSubmit(handleSubmit)}>
      <Stack>
        <TextInput label="Email" type="email" required {...form.getInputProps("email")} />
        <TextInput label="Full name" {...form.getInputProps("full_name")} />
        <PasswordInput
          label="Temporary password"
          description="Share it with the person; they can change it on their Account page."
          required
          {...form.getInputProps("password")}
        />
        <Checkbox
          label="Superuser (can manage users)"
          {...form.getInputProps("is_superuser", { type: "checkbox" })}
        />
        <Group justify="flex-end">
          <Button type="submit" loading={saving}>
            Create user
          </Button>
        </Group>
      </Stack>
    </form>
  );
}
