"use client";

// A team's students: add one, paste a list (e.g. copied from a spreadsheet),
// edit, or remove. The GitHub username ties a student's commits and pull
// requests to them on the team's Updates page.

import {
  ActionIcon,
  Alert,
  Anchor,
  Badge,
  Button,
  Group,
  Modal,
  Stack,
  Table,
  Text,
  Textarea,
  TextInput,
  Tooltip,
} from "@mantine/core";
import { notifications } from "@mantine/notifications";
import {
  IconBrandGithub,
  IconCheck,
  IconClipboardList,
  IconPencil,
  IconPlus,
  IconTrash,
  IconX,
} from "@tabler/icons-react";
import { Fragment, useState } from "react";

import { api } from "@/lib/api";
import type { MembersPasted, Team, TeamMember } from "@/lib/types";

const errorMessage = (err: unknown) => (err instanceof Error ? err.message : String(err));

type Draft = Pick<TeamMember, "name" | "email" | "github_username" | "role">;
const EMPTY: Draft = { name: "", email: "", github_username: "", role: "" };

export function TeamMembers({ team, onChange }: { team: Team; onChange: (team: Team) => void }) {
  const [editing, setEditing] = useState<number | "new" | null>(null);
  const [draft, setDraft] = useState<Draft>(EMPTY);
  const [busy, setBusy] = useState(false);
  const [pasting, setPasting] = useState(false);
  const base = `/teams/${team.id}/members`;

  function startEdit(m: TeamMember | null) {
    setEditing(m ? m.id : "new");
    setDraft(
      m
        ? { name: m.name, email: m.email, github_username: m.github_username, role: m.role }
        : EMPTY,
    );
  }

  async function save() {
    setBusy(true);
    try {
      const updated =
        editing === "new"
          ? await api.post<Team>(base, draft)
          : await api.patch<Team>(`${base}/${editing}`, draft);
      onChange(updated);
      setEditing(null);
    } catch (err) {
      notifications.show({ color: "red", message: errorMessage(err) });
    } finally {
      setBusy(false);
    }
  }

  async function remove(m: TeamMember) {
    try {
      onChange(await api.delete<Team>(`${base}/${m.id}`));
      notifications.show({ message: `Removed ${m.name} from ${team.name}` });
    } catch (err) {
      notifications.show({ color: "red", message: errorMessage(err) });
    }
  }

  const field = (key: keyof Draft, placeholder: string, width?: number) => (
    <TextInput
      size="xs"
      placeholder={placeholder}
      value={draft[key]}
      w={width}
      onChange={(e) => {
        const value = e.currentTarget.value;
        setDraft((d) => ({ ...d, [key]: value }));
      }}
      onKeyDown={(e) => {
        if (e.key === "Enter" && draft.name.trim()) save();
        if (e.key === "Escape") setEditing(null);
      }}
    />
  );

  const editRow = (
    <Table.Tr>
      <Table.Td>{field("name", "Name (required)")}</Table.Td>
      <Table.Td>{field("email", "email@school.edu")}</Table.Td>
      <Table.Td>{field("github_username", "GitHub username")}</Table.Td>
      <Table.Td>{field("role", "Role (optional)", 120)}</Table.Td>
      <Table.Td>
        <Group gap={2} justify="flex-end" wrap="nowrap">
          <ActionIcon
            variant="subtle"
            color="teal"
            aria-label="Save"
            loading={busy}
            disabled={!draft.name.trim()}
            onClick={save}
          >
            <IconCheck size={16} />
          </ActionIcon>
          <ActionIcon
            variant="subtle"
            color="gray"
            aria-label="Cancel"
            onClick={() => setEditing(null)}
          >
            <IconX size={16} />
          </ActionIcon>
        </Group>
      </Table.Td>
    </Table.Tr>
  );

  return (
    <Stack gap="sm">
      <Group justify="space-between">
        <Text fw={600}>
          Students{" "}
          <Text span c="dimmed" fw={400}>
            ({team.members.length})
          </Text>
        </Text>
        <Group gap="xs">
          <Button
            size="xs"
            variant="default"
            leftSection={<IconClipboardList size={14} />}
            onClick={() => setPasting(true)}
          >
            Paste a list
          </Button>
          <Button size="xs" leftSection={<IconPlus size={14} />} onClick={() => startEdit(null)}>
            Add student
          </Button>
        </Group>
      </Group>

      {team.members.length === 0 && editing !== "new" ? (
        <Text size="sm" c="dimmed">
          No students yet. Add them one at a time, or paste a list (one per line: name, email,
          GitHub username).
        </Text>
      ) : (
        <Table.ScrollContainer minWidth={640}>
          <Table verticalSpacing={6} fz="sm">
            <Table.Thead>
              <Table.Tr>
                <Table.Th>Name</Table.Th>
                <Table.Th>Email</Table.Th>
                <Table.Th>GitHub</Table.Th>
                <Table.Th>Role</Table.Th>
                <Table.Th />
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {team.members.map((m) =>
                editing === m.id ? (
                  <Fragment key={m.id}>{editRow}</Fragment>
                ) : (
                  <Table.Tr key={m.id}>
                    <Table.Td fw={500}>{m.name}</Table.Td>
                    <Table.Td>
                      {m.email ? (
                        <Anchor href={`mailto:${m.email}`} size="sm">
                          {m.email}
                        </Anchor>
                      ) : (
                        <Text size="sm" c="dimmed">
                          —
                        </Text>
                      )}
                    </Table.Td>
                    <Table.Td>
                      {m.github_username ? (
                        <Anchor
                          href={`https://github.com/${m.github_username}`}
                          target="_blank"
                          rel="noopener noreferrer"
                          size="sm"
                        >
                          <Group gap={4} component="span">
                            <IconBrandGithub size={14} />
                            {m.github_username}
                          </Group>
                        </Anchor>
                      ) : (
                        <Tooltip label="Add their GitHub username to see their commits on the Updates page">
                          <Text size="sm" c="dimmed">
                            —
                          </Text>
                        </Tooltip>
                      )}
                    </Table.Td>
                    <Table.Td>{m.role && <Badge variant="light">{m.role}</Badge>}</Table.Td>
                    <Table.Td>
                      <Group gap={2} justify="flex-end" wrap="nowrap">
                        <ActionIcon
                          variant="subtle"
                          color="gray"
                          aria-label={`Edit ${m.name}`}
                          onClick={() => startEdit(m)}
                        >
                          <IconPencil size={16} />
                        </ActionIcon>
                        <ActionIcon
                          variant="subtle"
                          color="red"
                          aria-label={`Remove ${m.name}`}
                          onClick={() => remove(m)}
                        >
                          <IconTrash size={16} />
                        </ActionIcon>
                      </Group>
                    </Table.Td>
                  </Table.Tr>
                ),
              )}
              {editing === "new" && editRow}
            </Table.Tbody>
          </Table>
        </Table.ScrollContainer>
      )}

      <Modal
        opened={pasting}
        onClose={() => setPasting(false)}
        title={`Add students to ${team.name}`}
        size="lg"
      >
        <PasteForm team={team} onChange={onChange} onClose={() => setPasting(false)} />
      </Modal>
    </Stack>
  );
}

export function PasteForm({
  team,
  onChange,
  onClose,
}: {
  team: Team;
  onChange: (team: Team) => void;
  onClose: () => void;
}) {
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [skipped, setSkipped] = useState<string[]>([]);

  async function submit() {
    setBusy(true);
    try {
      const r = await api.post<MembersPasted>(`/teams/${team.id}/members/paste`, { text });
      notifications.show({
        color: r.skipped.length ? "orange" : "teal",
        message: `Added ${r.added} student${r.added === 1 ? "" : "s"} to ${team.name}`,
      });
      onChange(r.team);
      if (r.skipped.length) {
        // Stay open, showing what wasn't added (and leaving those lines to fix).
        setSkipped(r.skipped);
        setText(r.skipped.map((line) => line.split(":")[0]).join("\n"));
      } else {
        onClose();
      }
    } catch (err) {
      notifications.show({ color: "red", message: errorMessage(err) });
    } finally {
      setBusy(false);
    }
  }

  return (
    <Stack>
      <Text size="sm" c="dimmed">
        One student per line: name, email, GitHub username, and role, separated by commas or tabs
        (so you can paste straight from a spreadsheet), in any order. Only the name is required.
      </Text>
      <Textarea
        autosize
        minRows={6}
        ff="monospace"
        placeholder={"Ana Diaz, ana@school.edu, @anadiaz, PM\nBen Ito\tben@school.edu\tbenito"}
        value={text}
        onChange={(e) => setText(e.currentTarget.value)}
        data-autofocus
      />
      {skipped.length > 0 && (
        <Alert color="orange" title="Not added">
          {skipped.map((s) => (
            <Text key={s} size="sm">
              {s}
            </Text>
          ))}
        </Alert>
      )}
      <Group justify="flex-end">
        <Button onClick={submit} loading={busy} disabled={!text.trim()}>
          Add students
        </Button>
      </Group>
    </Stack>
  );
}
