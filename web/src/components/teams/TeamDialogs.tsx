"use client";

// The forms shown in a team card's pop-up dialogs: naming a team, adding and
// editing links, creating a team's repo/team/project, and deleting a team.

import {
  ActionIcon,
  Alert,
  Anchor,
  Button,
  Collapse,
  Divider,
  Group,
  Stack,
  Text,
  TextInput,
  Tooltip,
} from "@mantine/core";
import { useForm } from "@mantine/form";
import { notifications } from "@mantine/notifications";
import {
  IconAlertTriangle,
  IconPencil,
  IconPlus,
  IconSearch,
  IconTrash,
} from "@tabler/icons-react";
import Link from "next/link";
import { useState } from "react";

import { useAuth } from "@/components/AuthProvider";
import { api } from "@/lib/api";
import { apiKeysPath } from "@/lib/paths";
import type { Team, TeamLink, TeamService, TeamServiceCreated } from "@/lib/types";
import { ToolIcon } from "@/modules/registry";

const URL_PATTERN = /^https?:\/\/\S+$/i;
const checkUrl = (v: string) =>
  URL_PATTERN.test(v.trim()) ? null : "Enter a full web address starting with https://";

const errorMessage = (err: unknown) => (err instanceof Error ? err.message : String(err));

// --- Team name (add / rename) -------------------------------------------------

export function TeamNameForm({
  initialName = "",
  submitLabel,
  onSubmit,
}: {
  initialName?: string;
  submitLabel: string;
  onSubmit: (name: string) => Promise<void>;
}) {
  const [saving, setSaving] = useState(false);
  const form = useForm({
    initialValues: { name: initialName },
    validate: { name: (v) => (v.trim() ? null : "Enter a team name") },
  });

  async function handleSubmit({ name }: { name: string }) {
    setSaving(true);
    try {
      await onSubmit(name.trim());
    } catch (err) {
      form.setFieldError("name", errorMessage(err));
    } finally {
      setSaving(false);
    }
  }

  return (
    <form onSubmit={form.onSubmit(handleSubmit)}>
      <Stack>
        <TextInput
          label="Team name"
          placeholder="Team Alpha"
          maxLength={100}
          required
          data-autofocus
          {...form.getInputProps("name")}
        />
        <Group justify="flex-end">
          <Button type="submit" loading={saving}>
            {submitLabel}
          </Button>
        </Group>
      </Stack>
    </form>
  );
}

// --- One link (add / edit) ----------------------------------------------------

export interface LinkValues {
  label: string;
  url: string;
}

export function LinkForm({
  initial,
  withLabel = true,
  urlPlaceholder = "https://",
  submitLabel,
  onSubmit,
  onCancel,
}: {
  initial?: LinkValues;
  /** Links to built-in services (GitHub, ...) are named after the service, so have no label field. */
  withLabel?: boolean;
  urlPlaceholder?: string;
  submitLabel: string;
  onSubmit: (values: LinkValues) => Promise<void>;
  onCancel?: () => void;
}) {
  const [saving, setSaving] = useState(false);
  const form = useForm({
    initialValues: initial ?? { label: "", url: "" },
    validate: {
      label: (v) => (!withLabel || v.trim() ? null : "Give the link a name"),
      url: checkUrl,
    },
  });

  async function handleSubmit(values: LinkValues) {
    setSaving(true);
    try {
      await onSubmit({ label: values.label.trim(), url: values.url.trim() });
    } catch (err) {
      form.setFieldError("url", errorMessage(err));
    } finally {
      setSaving(false);
    }
  }

  return (
    <form onSubmit={form.onSubmit(handleSubmit)}>
      <Stack gap="sm">
        {withLabel && (
          <TextInput
            label="Name"
            placeholder="Figma, Slack, Docs, ..."
            maxLength={100}
            required
            data-autofocus
            {...form.getInputProps("label")}
          />
        )}
        <TextInput
          label="Link"
          placeholder={urlPlaceholder}
          required
          data-autofocus={!withLabel || undefined}
          {...form.getInputProps("url")}
        />
        <Group justify="flex-end" gap="xs">
          {onCancel && (
            <Button variant="default" onClick={onCancel}>
              Cancel
            </Button>
          )}
          <Button type="submit" loading={saving}>
            {submitLabel}
          </Button>
        </Group>
      </Stack>
    </form>
  );
}

// --- Create (or find) a team's repo / Linear team / Coolify server -------------

export function CreateServiceDialog({
  team,
  service,
  onDone,
}: {
  team: Team;
  service: TeamService;
  onDone: (team: Team) => void;
}) {
  const { user } = useAuth();
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [linkExisting, setLinkExisting] = useState(false);
  const what = `${service.name} ${service.resource_name}`;

  // Superusers can add shared keys too; everyone else only their own.
  const canAddKeys =
    service.missing_user_credentials.length > 0 ||
    (user?.is_superuser && service.missing_system_credentials.length > 0);

  async function create() {
    setCreating(true);
    setError(null);
    try {
      const result = await api.post<TeamServiceCreated>(`/teams/${team.id}/services/${service.id}`);
      const link = result.team.links.find((l) => l.service_id === service.id);
      notifications.show({
        color: "teal",
        title: team.name,
        message: (
          <>
            {result.message}{" "}
            {link && (
              <Anchor href={link.url} target="_blank" rel="noopener noreferrer" size="sm">
                Open it
              </Anchor>
            )}
          </>
        ),
      });
      onDone(result.team);
    } catch (err) {
      setError(errorMessage(err));
      setCreating(false);
    }
  }

  async function saveExisting({ url }: LinkValues) {
    const updated = await api.post<Team>(`/teams/${team.id}/links`, {
      service_id: service.id,
      url,
    });
    notifications.show({ message: `Linked ${team.name}'s ${what}` });
    onDone(updated);
  }

  return (
    <Stack>
      {service.configured ? (
        <>
          <Text size="sm">
            {service.can_create ? "Create" : "Find"} {team.name}&apos;s {what}?
          </Text>
          <Text size="sm" c="dimmed">
            {service.summary}
          </Text>
          {error && (
            <Alert color="red" icon={<IconAlertTriangle />} title="That didn't work">
              {error}
            </Alert>
          )}
          <Group justify="flex-end">
            <Button
              leftSection={service.can_create ? <IconPlus size={16} /> : <IconSearch size={16} />}
              loading={creating}
              onClick={create}
            >
              {service.can_create ? `Create ${service.resource_name}` : "Find it"}
            </Button>
          </Group>
        </>
      ) : (
        <Alert
          color="yellow"
          icon={<IconAlertTriangle />}
          title={`${service.name} isn't set up yet`}
        >
          <Text size="sm">{service.message}</Text>
          {canAddKeys && (
            <Button component={Link} href={apiKeysPath(user)} size="xs" mt="sm" variant="white">
              Add API key
            </Button>
          )}
        </Alert>
      )}

      <Divider />
      <Anchor component="button" type="button" size="sm" onClick={() => setLinkExisting((v) => !v)}>
        Already have a {what} for this team? Link it instead
      </Anchor>
      <Collapse expanded={linkExisting}>
        <LinkForm
          withLabel={false}
          urlPlaceholder={`Paste the ${service.resource_name}'s ${service.name} address`}
          submitLabel="Link it"
          onSubmit={saveExisting}
        />
      </Collapse>
    </Stack>
  );
}

// --- Edit a team's links ------------------------------------------------------

export function EditLinksDialog({
  team,
  services,
  onChange,
}: {
  team: Team;
  services: TeamService[];
  onChange: (team: Team) => void;
}) {
  const [editingId, setEditingId] = useState<number | null>(null);
  const [removingId, setRemovingId] = useState<number | null>(null);
  const serviceFor = (link: TeamLink) => services.find((s) => s.id === link.service_id);

  async function save(link: TeamLink, values: LinkValues) {
    const changes = serviceFor(link) ? { url: values.url } : values;
    onChange(await api.patch<Team>(`/teams/${team.id}/links/${link.id}`, changes));
    setEditingId(null);
  }

  async function remove(link: TeamLink) {
    setRemovingId(link.id);
    try {
      onChange(await api.delete<Team>(`/teams/${team.id}/links/${link.id}`));
      const service = serviceFor(link);
      notifications.show({
        message: service
          ? `Removed the ${service.name} link. The ${service.resource_name} itself wasn't changed.`
          : `Removed ${link.label}`,
      });
    } catch (err) {
      notifications.show({ color: "red", message: errorMessage(err) });
    } finally {
      setRemovingId(null);
    }
  }

  if (team.links.length === 0) {
    return (
      <Text size="sm" c="dimmed">
        This team has no links yet.
      </Text>
    );
  }

  return (
    <Stack gap="md">
      {team.links.map((link) => {
        const service = serviceFor(link);
        const name = service?.name ?? link.label;

        if (editingId === link.id) {
          return (
            <LinkForm
              key={link.id}
              initial={{ label: link.label, url: link.url }}
              withLabel={!service}
              submitLabel="Save"
              onSubmit={(values) => save(link, values)}
              onCancel={() => setEditingId(null)}
            />
          );
        }
        return (
          <Group key={link.id} justify="space-between" wrap="nowrap" gap="xs">
            <Group gap="sm" wrap="nowrap" style={{ minWidth: 0 }}>
              <ToolIcon toolId={link.service_id} size={18} stroke={1.5} style={{ flexShrink: 0 }} />
              <div style={{ minWidth: 0 }}>
                <Text size="sm" fw={500}>
                  {name}
                  {service && link.label !== service.name && (
                    <Text span size="sm" c="dimmed" fw={400}>
                      {" "}
                      · {link.label}
                    </Text>
                  )}
                </Text>
                <Anchor
                  href={link.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  size="xs"
                  c="dimmed"
                  display="block"
                  truncate
                >
                  {link.url}
                </Anchor>
              </div>
            </Group>
            <Group gap={4} wrap="nowrap">
              <Tooltip label="Edit">
                <ActionIcon
                  variant="subtle"
                  color="gray"
                  aria-label={`Edit ${name} link`}
                  onClick={() => setEditingId(link.id)}
                >
                  <IconPencil size={16} />
                </ActionIcon>
              </Tooltip>
              <Tooltip label="Remove link">
                <ActionIcon
                  variant="subtle"
                  color="red"
                  aria-label={`Remove ${name} link`}
                  loading={removingId === link.id}
                  onClick={() => remove(link)}
                >
                  <IconTrash size={16} />
                </ActionIcon>
              </Tooltip>
            </Group>
          </Group>
        );
      })}
      <Text size="xs" c="dimmed">
        Removing a link only removes it from the workbench. Nothing is deleted in GitHub, Linear,
        Coolify, or anywhere else.
      </Text>
    </Stack>
  );
}

// --- Delete a team ------------------------------------------------------------

export function DeleteTeamDialog({
  team,
  onCancel,
  onDeleted,
}: {
  team: Team;
  onCancel: () => void;
  onDeleted: () => void;
}) {
  const [deleting, setDeleting] = useState(false);

  async function handleDelete() {
    setDeleting(true);
    try {
      await api.delete(`/teams/${team.id}`);
      notifications.show({ message: `Deleted ${team.name}` });
      onDeleted();
    } catch (err) {
      notifications.show({ color: "red", message: errorMessage(err) });
      setDeleting(false);
    }
  }

  return (
    <Stack>
      <Text size="sm">
        Delete <b>{team.name}</b> and its links from the workbench?
      </Text>
      <Text size="sm" c="dimmed">
        Nothing is deleted in GitHub, Linear, Coolify, or anywhere else. The team&apos;s repository,
        Linear team, and project stay where they are.
      </Text>
      <Group justify="flex-end" gap="xs">
        <Button variant="default" onClick={onCancel}>
          Cancel
        </Button>
        <Button color="red" loading={deleting} onClick={handleDelete}>
          Delete team
        </Button>
      </Group>
    </Stack>
  );
}
