"use client";

// A list of API keys / tokens with "Add", "Replace", and "Remove" actions.
// Used on the Account page (personal keys) and in System settings (system-wide
// keys). Saved values are never shown; the API only tells us whether a key is
// set and its last 4 characters.

import {
  Alert,
  Anchor,
  Badge,
  Button,
  Card,
  Group,
  Modal,
  PasswordInput,
  Skeleton,
  Stack,
  Text,
} from "@mantine/core";
import { useForm } from "@mantine/form";
import { notifications } from "@mantine/notifications";
import { IconAlertTriangle, IconExternalLink, IconKey } from "@tabler/icons-react";
import { useEffect, useState } from "react";

import { api } from "@/lib/api";
import { formatDate } from "@/lib/format";
import type { CredentialStatus } from "@/lib/types";

interface Props {
  /** "/credentials/me" or "/credentials/system" */
  endpoint: string;
  emptyMessage?: string;
}

export function CredentialList({ endpoint, emptyMessage = "No API keys to configure." }: Props) {
  const [items, setItems] = useState<CredentialStatus[] | null>(null);
  const [editing, setEditing] = useState<CredentialStatus | null>(null);
  const [removing, setRemoving] = useState<CredentialStatus | null>(null);

  useEffect(() => {
    api
      .get<CredentialStatus[]>(endpoint)
      .then(setItems)
      .catch((err: Error) => notifications.show({ color: "red", message: err.message }));
  }, [endpoint]);

  function replaceItem(updated: CredentialStatus) {
    setItems((list) => list?.map((c) => (c.key === updated.key ? updated : c)) ?? null);
  }

  if (items === null) return <Skeleton h={120} />;
  if (items.length === 0) return <Text c="dimmed">{emptyMessage}</Text>;

  return (
    <Stack>
      {items.map((c) => (
        <CredentialCard
          key={c.key}
          credential={c}
          onEdit={() => setEditing(c)}
          onRemove={() => setRemoving(c)}
        />
      ))}

      <Modal
        opened={editing !== null}
        onClose={() => setEditing(null)}
        title={editing ? `${editing.is_set ? "Replace" : "Add"} ${editing.label}` : ""}
      >
        {editing && (
          <EditForm
            endpoint={endpoint}
            credential={editing}
            onSaved={(updated) => {
              replaceItem(updated);
              setEditing(null);
            }}
          />
        )}
      </Modal>

      <Modal opened={removing !== null} onClose={() => setRemoving(null)} title="Remove key?">
        {removing && (
          <RemoveConfirm
            endpoint={endpoint}
            credential={removing}
            onCancel={() => setRemoving(null)}
            onRemoved={() => {
              replaceItem({ ...removing, is_set: false, hint: "", updated_at: null });
              setRemoving(null);
            }}
          />
        )}
      </Modal>
    </Stack>
  );
}

function CredentialCard({
  credential: c,
  onEdit,
  onRemove,
}: {
  credential: CredentialStatus;
  onEdit: () => void;
  onRemove: () => void;
}) {
  return (
    <Card withBorder padding="md">
      <Group justify="space-between" align="flex-start" wrap="nowrap" gap="md">
        <Stack gap={4} style={{ flex: 1, minWidth: 0 }}>
          <Group gap="xs">
            <IconKey size={16} stroke={1.5} />
            <Text fw={600}>{c.label}</Text>
            {c.is_set && c.readable && (
              <Badge color="teal" variant="light">
                Saved
              </Badge>
            )}
            {c.is_set && !c.readable && (
              <Badge color="orange" variant="light">
                Needs re-entry
              </Badge>
            )}
            {!c.is_set && (
              <Badge color="gray" variant="light">
                Not set
              </Badge>
            )}
          </Group>
          <Text size="sm" c="dimmed">
            {c.description}
          </Text>
          {c.is_set && c.updated_at && (
            <Text size="xs" c="dimmed">
              {c.hint ? `Ends in …${c.hint} · ` : ""}Updated {formatDate(c.updated_at)}
            </Text>
          )}
          {c.is_set && !c.readable && (
            <Alert color="orange" icon={<IconAlertTriangle />} p="xs" mt={4}>
              This key was saved with a different server secret and can&apos;t be read. Replace it
              to keep using it.
            </Alert>
          )}
          {c.help_url && (
            <Anchor href={c.help_url} target="_blank" rel="noreferrer" size="xs">
              <Group gap={4} component="span">
                Where do I get this? <IconExternalLink size={12} />
              </Group>
            </Anchor>
          )}
        </Stack>

        <Group gap="xs" wrap="nowrap">
          {c.is_set && (
            <Button variant="subtle" color="red" size="xs" onClick={onRemove}>
              Remove
            </Button>
          )}
          <Button variant={c.is_set ? "default" : "filled"} size="xs" onClick={onEdit}>
            {c.is_set ? "Replace" : "Add"}
          </Button>
        </Group>
      </Group>
    </Card>
  );
}

function EditForm({
  endpoint,
  credential,
  onSaved,
}: {
  endpoint: string;
  credential: CredentialStatus;
  onSaved: (c: CredentialStatus) => void;
}) {
  const [saving, setSaving] = useState(false);
  const form = useForm({
    initialValues: { value: "" },
    validate: { value: (v) => (v.trim() ? null : "Paste the key") },
  });

  async function handleSubmit({ value }: { value: string }) {
    setSaving(true);
    try {
      const updated = await api.put<CredentialStatus>(`${endpoint}/${credential.key}`, { value });
      notifications.show({ color: "teal", message: `${credential.label} saved` });
      onSaved(updated);
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
          {credential.description}
        </Text>
        <PasswordInput
          label={credential.label}
          placeholder={credential.placeholder}
          description="Stored encrypted. It can't be viewed again after saving, only replaced."
          autoComplete="off"
          data-autofocus
          {...form.getInputProps("value")}
        />
        <Group justify="flex-end">
          <Button type="submit" loading={saving}>
            Save
          </Button>
        </Group>
      </Stack>
    </form>
  );
}

function RemoveConfirm({
  endpoint,
  credential,
  onCancel,
  onRemoved,
}: {
  endpoint: string;
  credential: CredentialStatus;
  onCancel: () => void;
  onRemoved: () => void;
}) {
  const [busy, setBusy] = useState(false);

  async function remove() {
    setBusy(true);
    try {
      await api.delete(`${endpoint}/${credential.key}`);
      notifications.show({ message: `${credential.label} removed` });
      onRemoved();
    } catch (err) {
      notifications.show({ color: "red", message: (err as Error).message });
    } finally {
      setBusy(false);
    }
  }

  return (
    <Stack>
      <Text size="sm">
        Remove the saved <b>{credential.label}</b>? Features that depend on it will stop working
        until a new one is added.
        {credential.scope === "system" && " This affects every user."}
      </Text>
      <Group justify="flex-end">
        <Button variant="default" onClick={onCancel}>
          Cancel
        </Button>
        <Button color="red" loading={busy} onClick={remove}>
          Remove
        </Button>
      </Group>
    </Stack>
  );
}
