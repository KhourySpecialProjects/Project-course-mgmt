"use client";

// "Advanced: Coolify API" on a team's Coolify panel: call any route of the team's
// Coolify API (everything Coolify's MCP does goes through these same routes), for
// the things the panel has no screen for: backups, rollbacks, scheduled tasks,
// domains, and so on. Reading is open to everyone; changes need a superuser.

import {
  Alert,
  Anchor,
  Badge,
  Button,
  Card,
  Code,
  Collapse,
  Group,
  Modal,
  ScrollArea,
  Select,
  Stack,
  Text,
  Textarea,
  TextInput,
} from "@mantine/core";
import { IconChevronDown, IconChevronRight, IconSend, IconTerminal2 } from "@tabler/icons-react";
import { useState } from "react";

import { useAuth } from "@/components/AuthProvider";
import { api } from "@/lib/api";
import type { CoolifyResource, CoolifyServer } from "@/lib/types";
import { errorMessage } from "@/modules/coolify/parts";

type Method = "GET" | "POST" | "PATCH" | "PUT" | "DELETE";

interface Example {
  label: string;
  method: Method;
  path: string;
  body?: string;
}

function examples(resources: CoolifyResource[], servers: CoolifyServer[]): Example[] {
  const app = resources.find((r) => r.kind === "applications");
  const db = resources.find((r) => r.kind === "databases");
  const server = servers[0];
  const list: Example[] = [
    { label: "This Coolify team", method: "GET", path: "/team" },
    { label: "All resources", method: "GET", path: "/resources" },
    { label: "Running deployments", method: "GET", path: "/deployments" },
    { label: "Projects", method: "GET", path: "/projects" },
  ];
  if (server) {
    list.push(
      {
        label: `Domains on ${server.name}`,
        method: "GET",
        path: `/servers/${server.uuid}/domains`,
      },
      {
        label: `Resources on ${server.name}`,
        method: "GET",
        path: `/servers/${server.uuid}/resources`,
      },
    );
  }
  if (app) {
    list.push(
      { label: `${app.name}: details`, method: "GET", path: `/applications/${app.uuid}` },
      {
        label: `${app.name}: scheduled tasks`,
        method: "GET",
        path: `/applications/${app.uuid}/scheduled-tasks`,
      },
      {
        label: `${app.name}: deploy (force rebuild)`,
        method: "POST",
        path: `/deploy?uuid=${app.uuid}&force=true`,
      },
    );
  }
  if (db) {
    list.push(
      { label: `${db.name}: details`, method: "GET", path: `/databases/${db.uuid}` },
      { label: `${db.name}: backups`, method: "GET", path: `/databases/${db.uuid}/backups` },
    );
  }
  return list;
}

export function ApiConsole({
  teamId,
  resources,
  servers,
}: {
  teamId: number;
  resources: CoolifyResource[];
  servers: CoolifyServer[];
}) {
  const { user } = useAuth();
  const [open, setOpen] = useState(false);
  const [method, setMethod] = useState<Method>("GET");
  const [path, setPath] = useState("/resources");
  const [body, setBody] = useState("");
  const [sending, setSending] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [result, setResult] = useState<{ status: number; data: unknown } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const canWrite = Boolean(user?.is_superuser);
  const list = examples(resources, servers);

  async function send() {
    setSending(true);
    setError(null);
    setResult(null);
    try {
      let parsed: unknown = undefined;
      if (method !== "GET" && body.trim()) parsed = JSON.parse(body);
      setResult(
        await api.post<{ status: number; data: unknown }>(`/tools/coolify/teams/${teamId}/api`, {
          method,
          path,
          body: parsed,
        }),
      );
    } catch (err) {
      setError(
        err instanceof SyntaxError
          ? `The body isn't valid JSON: ${err.message}`
          : errorMessage(err),
      );
    } finally {
      setSending(false);
      setConfirming(false);
    }
  }

  return (
    <Card withBorder>
      <Group
        justify="space-between"
        style={{ cursor: "pointer" }}
        onClick={() => setOpen((v) => !v)}
      >
        <Group gap="xs">
          {open ? <IconChevronDown size={16} /> : <IconChevronRight size={16} />}
          <IconTerminal2 size={18} />
          <Text fw={600}>Advanced: Coolify API</Text>
        </Group>
        <Text size="xs" c="dimmed">
          For anything without a button here: backups, rollbacks, scheduled tasks, domains, …
        </Text>
      </Group>
      <Collapse expanded={open}>
        <Stack gap="sm" mt="md">
          <Text size="sm" c="dimmed">
            Calls this team&apos;s Coolify API with its own token, the same routes Coolify&apos;s
            MCP uses. See the{" "}
            <Anchor
              href="https://coolify.io/docs/api-reference"
              target="_blank"
              rel="noopener noreferrer"
              size="sm"
            >
              Coolify API reference
            </Anchor>{" "}
            for every route.{" "}
            {canWrite
              ? "Anything other than GET changes Coolify, so it asks first."
              : "Only superusers can send changes (anything other than GET)."}
          </Text>
          <Select
            label="Examples"
            placeholder="Pick one to fill in the form"
            data={list.map((e, i) => ({ value: String(i), label: `${e.method}  ${e.label}` }))}
            onChange={(v) => {
              const e = v === null ? undefined : list[Number(v)];
              if (!e) return;
              setMethod(e.method);
              setPath(e.path);
              setBody(e.body ?? "");
            }}
            clearable
          />
          <Group align="flex-end" gap="xs" wrap="nowrap">
            <Select
              label="Method"
              w={110}
              data={["GET", "POST", "PATCH", "PUT", "DELETE"]}
              value={method}
              onChange={(v) => setMethod((v as Method) ?? "GET")}
              allowDeselect={false}
            />
            <TextInput
              label="Path (under /api/v1)"
              value={path}
              onChange={(e) => setPath(e.currentTarget.value)}
              ff="monospace"
              style={{ flex: 1 }}
            />
            <Button
              leftSection={<IconSend size={14} />}
              loading={sending}
              disabled={!path.trim() || (method !== "GET" && !canWrite)}
              onClick={() => (method === "GET" ? send() : setConfirming(true))}
            >
              Send
            </Button>
          </Group>
          {method !== "GET" && (
            <Textarea
              label="JSON body (optional)"
              autosize
              minRows={3}
              ff="monospace"
              value={body}
              onChange={(e) => setBody(e.currentTarget.value)}
              placeholder='{"key": "value"}'
            />
          )}
          {error && <Alert color="red">{error}</Alert>}
          {result && (
            <Stack gap={4}>
              <Group gap="xs">
                <Text size="sm" fw={500}>
                  Response
                </Text>
                <Badge color={result.status < 300 ? "teal" : "red"} variant="light">
                  {result.status}
                </Badge>
              </Group>
              <ScrollArea.Autosize mah={420} type="auto">
                <Code block fz="xs">
                  {JSON.stringify(result.data, null, 2) ?? "(empty)"}
                </Code>
              </ScrollArea.Autosize>
            </Stack>
          )}
        </Stack>
      </Collapse>

      <Modal opened={confirming} onClose={() => setConfirming(false)} title="Change Coolify?">
        <Stack>
          <Text size="sm">
            This sends <Code>{method}</Code> <Code>{path}</Code> to this team&apos;s Coolify, which
            can change or delete things there.
          </Text>
          <Group justify="flex-end" gap="xs">
            <Button variant="default" onClick={() => setConfirming(false)}>
              Cancel
            </Button>
            <Button color="red" loading={sending} onClick={send}>
              Send it
            </Button>
          </Group>
        </Stack>
      </Modal>
    </Card>
  );
}
