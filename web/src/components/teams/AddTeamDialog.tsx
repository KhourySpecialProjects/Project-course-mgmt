"use client";

// The "Add team" form: everything at once, and only the name is required.
//
// As the name is typed, it asks the API what GitHub, Linear, Coolify, ... already
// have for that name (GET /api/teams/lookup) and fills in the links it finds.
// Anything that doesn't exist yet is ticked to be created when the team is added
// (untick it to leave it for later). Any link can also be typed in or changed by hand.

import {
  ActionIcon,
  Alert,
  Button,
  Checkbox,
  Divider,
  Group,
  Loader,
  Stack,
  Text,
  Textarea,
  TextInput,
} from "@mantine/core";
import { useDebouncedCallback } from "@mantine/hooks";
import { notifications } from "@mantine/notifications";
import {
  IconAlertTriangle,
  IconCircleCheck,
  IconInfoCircle,
  IconPlus,
  IconTrash,
} from "@tabler/icons-react";
import { type FormEvent, type ReactNode, useRef, useState } from "react";

import { api } from "@/lib/api";
import type {
  MembersPasted,
  ServiceLookup,
  Team,
  TeamLookup,
  TeamService,
  TeamServiceCreated,
} from "@/lib/types";
import { ToolIcon } from "@/modules/registry";

const URL_PATTERN = /^https?:\/\/\S+$/i;
const tidy = (s: string) => s.trim().replace(/\s+/g, " ");
const errorMessage = (err: unknown) => (err instanceof Error ? err.message : String(err));

interface ServiceRow {
  url: string;
  /** Set when `url` came from the lookup, so the API can spot one repo going to two teams. */
  externalId: string;
  /** Typed in by hand: lookup results no longer overwrite it. */
  edited: boolean;
  /** Create it when the team is added. */
  create: boolean;
}

const EMPTY_ROW: ServiceRow = { url: "", externalId: "", edited: false, create: false };

interface CustomRow {
  key: number;
  label: string;
  url: string;
}

/** Fill in every row the user hasn't typed into from the lookup results. */
function applyLookup(
  rows: Record<string, ServiceRow>,
  lookup: TeamLookup,
  services: TeamService[],
) {
  const next = { ...rows };
  for (const result of lookup.services) {
    const row = next[result.service_id] ?? EMPTY_ROW;
    if (row.edited) continue;
    const usable = result.found && !result.linked_team ? result.found : null;
    const canCreate = services.some((s) => s.id === result.service_id && s.can_create);
    next[result.service_id] = {
      url: usable?.url ?? "",
      externalId: usable?.external_id ?? "",
      edited: false,
      // Nothing there yet (and nothing went wrong looking): create it, unless unticked.
      create: canCreate && result.configured && !result.error && !result.found,
    };
  }
  return next;
}

export function AddTeamDialog({
  services,
  onAdded,
}: {
  services: TeamService[];
  onAdded: (team: Team) => void;
}) {
  const [name, setName] = useState("");
  const [nameError, setNameError] = useState<string | null>(null);
  const [lookup, setLookup] = useState<TeamLookup | null>(null);
  const [lookingUp, setLookingUp] = useState(false);
  const [lookupError, setLookupError] = useState<string | null>(null);
  const [rows, setRows] = useState<Record<string, ServiceRow>>({});
  const [custom, setCustom] = useState<CustomRow[]>([]);
  const [students, setStudents] = useState("");
  const [progress, setProgress] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  // The name the newest lookup is for, so a slow, older answer is ignored.
  const latestName = useRef("");
  const nextKey = useRef(1);

  const cleanName = tidy(name);
  // Lookup results count only while they're for the name in the box.
  const current = lookup && lookup.name === cleanName ? lookup : null;
  const rowFor = (id: string) => rows[id] ?? EMPTY_ROW;
  const resultFor = (id: string) => current?.services.find((r) => r.service_id === id);

  const runLookup = useDebouncedCallback(async (value: string) => {
    try {
      const result = await api.get<TeamLookup>(`/teams/lookup?name=${encodeURIComponent(value)}`);
      if (latestName.current !== value) return;
      setLookup(result);
      setLookupError(null);
      setRows((current) => applyLookup(current, result, services));
    } catch (err) {
      if (latestName.current === value) setLookupError(errorMessage(err));
    } finally {
      if (latestName.current === value) setLookingUp(false);
    }
  }, 500);

  function changeName(value: string) {
    setName(value);
    setNameError(null);
    const clean = tidy(value);
    latestName.current = clean;
    if (!clean) {
      runLookup.cancel();
      setLookup(null);
      setLookingUp(false);
      // Forget what was filled in for the old name, but keep anything typed by hand.
      setRows((current) =>
        Object.fromEntries(Object.entries(current).filter(([, row]) => row.edited)),
      );
      return;
    }
    setLookingUp(true);
    runLookup(clean);
  }

  function changeRow(id: string, changes: Partial<ServiceRow>) {
    setRows((current) => ({ ...current, [id]: { ...(current[id] ?? EMPTY_ROW), ...changes } }));
  }

  function typeUrl(id: string, url: string) {
    const found = resultFor(id)?.found;
    changeRow(id, {
      url,
      edited: true,
      externalId: found && url.trim() === found.url ? found.external_id : "",
      create: false,
    });
  }

  function changeCustom(key: number, changes: Partial<CustomRow>) {
    setCustom((list) => list.map((row) => (row.key === key ? { ...row, ...changes } : row)));
  }

  const toCreate = services.filter((s) => rowFor(s.id).create && !rowFor(s.id).url.trim());
  const nameTaken = Boolean(current?.name_taken);

  function problems(): string | null {
    for (const s of services) {
      const url = rowFor(s.id).url.trim();
      if (url && !URL_PATTERN.test(url)) {
        return `${s.name}: enter a full web address starting with https://`;
      }
    }
    for (const row of custom) {
      const [label, url] = [row.label.trim(), row.url.trim()];
      if (!label && !url) continue;
      if (!label) return `Give the link ${url} a name, e.g. Figma or Slack.`;
      if (!URL_PATTERN.test(url))
        return `${label}: enter a full web address starting with https://`;
    }
    return null;
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    const clean = cleanName;
    if (!clean) {
      setNameError("Enter a team name");
      return;
    }
    const problem = problems();
    setFormError(problem);
    if (problem || nameTaken) return;

    const links = [
      ...services
        .filter((s) => rowFor(s.id).url.trim())
        .map((s) => {
          const url = rowFor(s.id).url.trim();
          const found = resultFor(s.id)?.found;
          return {
            service_id: s.id,
            url,
            external_id: rowFor(s.id).externalId,
            // What was found (e.g. "org/repo"), shown when hovering over the card's button.
            label: found && found.url === url ? found.label : "",
          };
        }),
      ...custom
        .filter((row) => row.label.trim() && row.url.trim())
        .map((row) => ({ label: row.label.trim(), url: row.url.trim() })),
    ];

    setProgress("Adding team...");
    let team: Team;
    try {
      team = await api.post<Team>("/teams", { name: clean, links });
    } catch (err) {
      setFormError(errorMessage(err));
      setProgress(null);
      return;
    }

    // The team exists now. Add its students and create the rest one by one; a failure
    // doesn't undo the team.
    const failures: string[] = [];
    if (students.trim()) {
      setProgress("Adding students...");
      try {
        const pasted = await api.post<MembersPasted>(`/teams/${team.id}/members/paste`, {
          text: students,
        });
        team = pasted.team;
        if (pasted.skipped.length)
          failures.push(`Students not added: ${pasted.skipped.join("; ")}.`);
      } catch (err) {
        failures.push(`Students: ${errorMessage(err)}`);
      }
    }
    for (const s of toCreate) {
      setProgress(`Creating ${s.name} ${s.resource_name}...`);
      try {
        const result = await api.post<TeamServiceCreated>(`/teams/${team.id}/services/${s.id}`);
        team = result.team;
        notifications.show({ color: "teal", message: result.message });
      } catch (err) {
        failures.push(`${s.name}: ${errorMessage(err)}`);
      }
    }
    if (failures.length > 0) {
      notifications.show({
        color: "red",
        title: `${team.name} was added, but not everything was created`,
        message: `${failures.join(" ")} Use the team's dashed buttons to try again.`,
        autoClose: false,
      });
    } else {
      notifications.show({ message: `Added ${team.name}` });
    }
    onAdded(team);
  }

  return (
    <form onSubmit={submit}>
      <Stack gap="md">
        <TextInput
          label="Team name"
          placeholder="Team Alpha"
          required
          maxLength={100}
          data-autofocus
          value={name}
          onChange={(e) => changeName(e.currentTarget.value)}
          error={nameError ?? (nameTaken ? "There's already a team with this name." : null)}
          description={
            services.length > 0
              ? `Type a name and the links below fill in from ${services.map((s) => s.name).join(", ")}.`
              : undefined
          }
          rightSection={lookingUp ? <Loader size="xs" /> : null}
        />

        {services.length > 0 && (
          <Stack gap="sm">
            <Divider label="Services (optional)" labelPosition="left" />
            {lookupError && (
              <Alert color="red" icon={<IconAlertTriangle />} p="xs">
                Couldn&apos;t look the name up: {lookupError}
              </Alert>
            )}
            {services.map((s) => (
              <ServiceField
                key={s.id}
                service={s}
                row={rowFor(s.id)}
                result={resultFor(s.id)}
                hasName={Boolean(cleanName)}
                lookingUp={lookingUp}
                onUrl={(url) => typeUrl(s.id, url)}
                onCreate={(create) => changeRow(s.id, { create })}
              />
            ))}
          </Stack>
        )}

        <Stack gap="xs">
          <Divider label="Students (optional)" labelPosition="left" />
          <Textarea
            aria-label="Students"
            autosize
            minRows={2}
            ff="monospace"
            placeholder={
              "One per line: name, email, GitHub username\nAna Diaz, ana@school.edu, @anadiaz"
            }
            value={students}
            onChange={(e) => setStudents(e.currentTarget.value)}
          />
        </Stack>

        <Stack gap="xs">
          <Divider label="Other links (optional)" labelPosition="left" />
          {custom.map((row) => (
            <Group key={row.key} gap="xs" wrap="nowrap" align="flex-start">
              <TextInput
                aria-label="Link name"
                placeholder="Figma, Slack, ..."
                w={150}
                maxLength={100}
                value={row.label}
                onChange={(e) => changeCustom(row.key, { label: e.currentTarget.value })}
              />
              <TextInput
                aria-label="Link address"
                placeholder="https://"
                style={{ flex: 1 }}
                value={row.url}
                onChange={(e) => changeCustom(row.key, { url: e.currentTarget.value })}
              />
              <ActionIcon
                variant="subtle"
                color="gray"
                size="lg"
                aria-label="Remove this link"
                onClick={() => setCustom((list) => list.filter((r) => r.key !== row.key))}
              >
                <IconTrash size={16} />
              </ActionIcon>
            </Group>
          ))}
          <Group>
            <Button
              variant="subtle"
              size="compact-sm"
              leftSection={<IconPlus size={14} />}
              onClick={() =>
                setCustom((list) => [...list, { key: nextKey.current++, label: "", url: "" }])
              }
            >
              Add a link
            </Button>
          </Group>
        </Stack>

        {formError && (
          <Alert color="red" icon={<IconAlertTriangle />}>
            {formError}
          </Alert>
        )}

        <Group justify="space-between" align="center" wrap="nowrap">
          <Text size="xs" c="dimmed">
            {progress ??
              (toCreate.length > 0
                ? `Also creates: ${toCreate.map((s) => `${s.name} ${s.resource_name}`).join(", ")}.`
                : "")}
          </Text>
          <Button type="submit" loading={progress !== null} disabled={nameTaken}>
            Add team
          </Button>
        </Group>
      </Stack>
    </form>
  );
}

function ServiceField({
  service,
  row,
  result,
  hasName,
  lookingUp,
  onUrl,
  onCreate,
}: {
  service: TeamService;
  row: ServiceRow;
  result: ServiceLookup | undefined;
  hasName: boolean;
  lookingUp: boolean;
  onUrl: (url: string) => void;
  onCreate: (create: boolean) => void;
}) {
  const what = `${service.name} ${service.resource_name}`;
  const taken = result?.found && result.linked_team ? result : null;
  const canCreate =
    service.can_create && service.configured && !row.url.trim() && !taken && !result?.error;

  let status: ReactNode;
  if (!hasName) {
    status = <Hint>Type a team name to look for its {service.resource_name}.</Hint>;
  } else if (lookingUp && !row.edited) {
    status = <Hint icon={<Loader size={12} />}>Looking in {service.name}...</Hint>;
  } else if (row.edited && row.url.trim()) {
    status = <Hint>Using the link you entered.</Hint>;
  } else if (result?.error) {
    status = (
      <Hint icon={<IconAlertTriangle size={14} />} color={result.configured ? "red" : "yellow"}>
        {result.error}
      </Hint>
    );
  } else if (taken) {
    status = (
      <Hint icon={<IconAlertTriangle size={14} />} color="orange">
        Found {taken.found?.label}, but it&apos;s already linked to {taken.linked_team}.
      </Hint>
    );
  } else if (result?.found) {
    status = (
      <Hint icon={<IconCircleCheck size={14} />} color="teal">
        Found {result.found.label}
      </Hint>
    );
  } else if (result) {
    status = <Hint icon={<IconInfoCircle size={14} />}>No {what} with this name yet.</Hint>;
  }

  return (
    <Stack gap={4}>
      <Group gap="xs" wrap="nowrap">
        <ToolIcon toolId={service.id} size={18} stroke={1.5} />
        <Text size="sm" fw={500}>
          {what}
        </Text>
      </Group>
      <TextInput
        aria-label={`${what} link`}
        placeholder="https:// (optional)"
        value={row.url}
        onChange={(e) => onUrl(e.currentTarget.value)}
      />
      {status}
      {canCreate && hasName && !(lookingUp && !row.edited) && (
        <Checkbox
          size="xs"
          label={`Create a new ${service.resource_name} when adding the team`}
          checked={row.create}
          onChange={(e) => onCreate(e.currentTarget.checked)}
        />
      )}
    </Stack>
  );
}

function Hint({
  children,
  icon,
  color = "dimmed",
}: {
  children: ReactNode;
  icon?: ReactNode;
  color?: string;
}) {
  return (
    <Group gap={6} wrap="nowrap" align="center" c={color}>
      {icon}
      <Text size="xs" c="inherit">
        {children}
      </Text>
    </Group>
  );
}
