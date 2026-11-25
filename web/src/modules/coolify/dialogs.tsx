"use client";

// Pop-up views for one Coolify resource: logs, deployments, environment
// variables, and security findings. Each loads its data when opened.

import {
  ActionIcon,
  Alert,
  Anchor,
  Badge,
  Button,
  Code,
  Group,
  Loader,
  ScrollArea,
  Stack,
  Table,
  Text,
  TextInput,
  Tooltip,
} from "@mantine/core";
import { notifications } from "@mantine/notifications";
import {
  IconAlertTriangle,
  IconCheck,
  IconEye,
  IconEyeOff,
  IconLock,
  IconPencil,
  IconPlus,
  IconRefresh,
  IconTrash,
  IconX,
} from "@tabler/icons-react";
import { useEffect, useState } from "react";

import { api } from "@/lib/api";
import { formatDateTime } from "@/lib/format";
import type {
  CoolifyActionResult,
  CoolifyDeployment,
  CoolifyDeploymentDetail,
  CoolifyEnv,
  CoolifyFindings,
  CoolifyResource,
} from "@/lib/types";
import { SecurityBadge, SeverityBadge, errorMessage } from "@/modules/coolify/parts";

interface Props {
  teamId: number;
  resource: CoolifyResource;
}

function Failure({ error }: { error: string }) {
  return (
    <Alert color="red" icon={<IconAlertTriangle />}>
      {error}
    </Alert>
  );
}

/** Loads `path` now and whenever `reload()` is called. */
function useLoad<T>(path: string) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [version, setVersion] = useState(0);
  useEffect(() => {
    let cancelled = false;
    api
      .get<T>(path)
      .then((d) => {
        if (!cancelled) {
          setData(d);
          setError(null);
        }
      })
      .catch((err) => !cancelled && setError(errorMessage(err)));
    return () => {
      cancelled = true;
    };
  }, [path, version]);
  return { data, error, setData, reload: () => setVersion((v) => v + 1) };
}

// --- Logs -------------------------------------------------------------------

export function LogsDialog({ teamId, resource }: Props) {
  const { data, error, reload } = useLoad<{ logs: string }>(
    `/tools/coolify/teams/${teamId}/applications/${resource.uuid}/logs?lines=500`,
  );
  return (
    <Stack>
      <Group justify="space-between">
        <Text size="sm" c="dimmed">
          The last 500 lines from {resource.name}&apos;s containers.
        </Text>
        <Button
          size="xs"
          variant="default"
          leftSection={<IconRefresh size={14} />}
          onClick={reload}
        >
          Refresh
        </Button>
      </Group>
      {error && <Failure error={error} />}
      {!data && !error && <Loader size="sm" />}
      {data && (
        <ScrollArea h={460} type="auto">
          <Code block fz="xs">
            {data.logs || "(no output)"}
          </Code>
        </ScrollArea>
      )}
    </Stack>
  );
}

// --- Deployments --------------------------------------------------------------

const DEPLOY_COLORS: Record<string, string> = {
  finished: "teal",
  failed: "red",
  in_progress: "blue",
  queued: "gray",
  cancelled: "gray",
  "cancelled-by-user": "gray",
};

export function DeploymentsDialog({ teamId, resource }: Props) {
  const base = `/tools/coolify/teams/${teamId}`;
  const list = useLoad<CoolifyDeployment[]>(`${base}/applications/${resource.uuid}/deployments`);
  const [selected, setSelected] = useState<string | null>(null);
  const [detail, setDetail] = useState<CoolifyDeploymentDetail | null>(null);
  const [detailError, setDetailError] = useState<string | null>(null);

  async function open(uuid: string) {
    setSelected(uuid);
    setDetail(null);
    setDetailError(null);
    try {
      setDetail(await api.get<CoolifyDeploymentDetail>(`${base}/deployments/${uuid}`));
    } catch (err) {
      setDetailError(errorMessage(err));
    }
  }

  async function cancel(uuid: string) {
    try {
      const r = await api.post<CoolifyActionResult>(`${base}/deployments/${uuid}/cancel`);
      notifications.show({ message: r.message });
      list.reload();
    } catch (err) {
      notifications.show({ color: "red", message: errorMessage(err) });
    }
  }

  return (
    <Stack>
      {list.error && <Failure error={list.error} />}
      {!list.data && !list.error && <Loader size="sm" />}
      {list.data?.length === 0 && (
        <Text size="sm" c="dimmed">
          No deployments yet.
        </Text>
      )}
      {list.data && list.data.length > 0 && (
        <Table highlightOnHover fz="sm">
          <Table.Tbody>
            {list.data.map((d) => (
              <Table.Tr
                key={d.uuid}
                style={{ cursor: "pointer" }}
                bg={selected === d.uuid ? "var(--mantine-color-default-hover)" : undefined}
                onClick={() => open(d.uuid)}
              >
                <Table.Td>
                  <Badge color={DEPLOY_COLORS[d.status] ?? "gray"} variant="light">
                    {d.status}
                  </Badge>
                </Table.Td>
                <Table.Td>
                  <Text size="sm" lineClamp={1}>
                    {d.commit_message || (d.commit ? d.commit.slice(0, 7) : "Manual deploy")}
                  </Text>
                </Table.Td>
                <Table.Td>
                  <Text size="xs" c="dimmed">
                    {d.created_at ? formatDateTime(d.created_at) : ""}
                  </Text>
                </Table.Td>
                <Table.Td>
                  {(d.status === "in_progress" || d.status === "queued") && (
                    <Button
                      size="compact-xs"
                      variant="light"
                      color="red"
                      onClick={(e) => {
                        e.stopPropagation();
                        cancel(d.uuid);
                      }}
                    >
                      Cancel
                    </Button>
                  )}
                </Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      )}
      {selected && (
        <Stack gap={4}>
          <Text size="sm" fw={500}>
            Deployment log
          </Text>
          {detailError && <Failure error={detailError} />}
          {!detail && !detailError && <Loader size="sm" />}
          {detail && (
            <ScrollArea h={320} type="auto">
              <Code block fz="xs">
                {detail.log.length === 0
                  ? "(no log)"
                  : detail.log.map((l, i) => (
                      <Text
                        key={i}
                        span
                        display="block"
                        ff="monospace"
                        fz="xs"
                        c={l.type === "stderr" ? "red" : undefined}
                      >
                        {l.output}
                      </Text>
                    ))}
              </Code>
            </ScrollArea>
          )}
        </Stack>
      )}
    </Stack>
  );
}

// --- Environment variables ------------------------------------------------------

export function EnvDialog({ teamId, resource }: Props) {
  const url = `/tools/coolify/teams/${teamId}/applications/${resource.uuid}/envs`;
  const { data, error, setData } = useLoad<CoolifyEnv[]>(url);
  const [shown, setShown] = useState<Set<string>>(new Set());
  const [editing, setEditing] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const [newKey, setNewKey] = useState("");
  const [newValue, setNewValue] = useState("");
  const [busy, setBusy] = useState(false);

  async function run(action: () => Promise<CoolifyEnv[]>, done: string) {
    setBusy(true);
    try {
      setData(await action());
      notifications.show({ message: `${done}. Redeploy ${resource.name} to use it.` });
      return true;
    } catch (err) {
      notifications.show({ color: "red", message: errorMessage(err) });
      return false;
    } finally {
      setBusy(false);
    }
  }

  const toggle = (uuid: string) =>
    setShown((s) => {
      const next = new Set(s);
      if (next.has(uuid)) next.delete(uuid);
      else next.add(uuid);
      return next;
    });

  return (
    <Stack>
      {error && <Failure error={error} />}
      {!data && !error && <Loader size="sm" />}
      {data && (
        <Table fz="sm" verticalSpacing={6}>
          <Table.Tbody>
            {data.map((env) => (
              <Table.Tr key={env.uuid}>
                <Table.Td w="35%">
                  <Code>{env.key}</Code>
                  {env.is_buildtime && (
                    <Badge size="xs" variant="outline" ml={6}>
                      build
                    </Badge>
                  )}
                </Table.Td>
                <Table.Td>
                  {editing === env.uuid ? (
                    <TextInput
                      size="xs"
                      value={draft}
                      onChange={(e) => setDraft(e.currentTarget.value)}
                      autoFocus
                    />
                  ) : env.is_shown_once ? (
                    <Group gap={4}>
                      <IconLock size={14} />
                      <Text size="xs" c="dimmed">
                        Locked in Coolify
                      </Text>
                    </Group>
                  ) : env.value === null ? (
                    <Text size="xs" c="dimmed">
                      Hidden (the token can&apos;t read secrets)
                    </Text>
                  ) : (
                    <Text size="sm" ff="monospace" style={{ wordBreak: "break-all" }}>
                      {shown.has(env.uuid) ? env.value || '""' : "••••••••"}
                    </Text>
                  )}
                </Table.Td>
                <Table.Td w={110}>
                  <Group gap={2} justify="flex-end" wrap="nowrap">
                    {editing === env.uuid ? (
                      <>
                        <ActionIcon
                          variant="subtle"
                          color="teal"
                          aria-label="Save"
                          loading={busy}
                          onClick={async () => {
                            const ok = await run(
                              () => api.patch<CoolifyEnv[]>(url, { key: env.key, value: draft }),
                              `Saved ${env.key}`,
                            );
                            if (ok) setEditing(null);
                          }}
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
                      </>
                    ) : (
                      <>
                        {env.value !== null && !env.is_shown_once && (
                          <ActionIcon
                            variant="subtle"
                            color="gray"
                            aria-label={shown.has(env.uuid) ? "Hide" : "Show"}
                            onClick={() => toggle(env.uuid)}
                          >
                            {shown.has(env.uuid) ? <IconEyeOff size={16} /> : <IconEye size={16} />}
                          </ActionIcon>
                        )}
                        <Tooltip label="Change value">
                          <ActionIcon
                            variant="subtle"
                            color="gray"
                            aria-label={`Change ${env.key}`}
                            onClick={() => {
                              setEditing(env.uuid);
                              setDraft(env.value ?? "");
                            }}
                          >
                            <IconPencil size={16} />
                          </ActionIcon>
                        </Tooltip>
                        <Tooltip label="Delete">
                          <ActionIcon
                            variant="subtle"
                            color="red"
                            aria-label={`Delete ${env.key}`}
                            onClick={() =>
                              run(
                                () => api.delete<CoolifyEnv[]>(`${url}/${env.uuid}`),
                                `Deleted ${env.key}`,
                              )
                            }
                          >
                            <IconTrash size={16} />
                          </ActionIcon>
                        </Tooltip>
                      </>
                    )}
                  </Group>
                </Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      )}
      {data && (
        <Group align="flex-end" gap="xs" wrap="nowrap">
          <TextInput
            label="New variable"
            placeholder="NAME"
            value={newKey}
            onChange={(e) => setNewKey(e.currentTarget.value)}
            w={180}
          />
          <TextInput
            label="Value"
            value={newValue}
            onChange={(e) => setNewValue(e.currentTarget.value)}
            style={{ flex: 1 }}
          />
          <Button
            leftSection={<IconPlus size={14} />}
            disabled={!newKey.trim()}
            loading={busy}
            onClick={async () => {
              const ok = await run(
                () => api.post<CoolifyEnv[]>(url, { key: newKey.trim(), value: newValue }),
                `Added ${newKey.trim()}`,
              );
              if (ok) {
                setNewKey("");
                setNewValue("");
              }
            }}
          >
            Add
          </Button>
        </Group>
      )}
    </Stack>
  );
}

// --- Security findings ------------------------------------------------------------

export function FindingsDialog({ teamId, resource }: Props) {
  const { data, error } = useLoad<CoolifyFindings>(
    `/tools/coolify/teams/${teamId}/resources/${resource.kind}/${resource.uuid}/vulnerabilities`,
  );
  return (
    <Stack>
      {error && <Failure error={error} />}
      {!data && !error && <Loader size="sm" />}
      {data && (
        <>
          <Group gap="xs">
            <SecurityBadge security={data.security} />
            {data.security?.action && (
              <Text size="sm" c="dimmed">
                {data.security.action}
              </Text>
            )}
          </Group>
          {data.images.length > 0 && (
            <Text size="xs" c="dimmed">
              Images: {data.images.join(", ")}
            </Text>
          )}
          {data.findings.length === 0 ? (
            <Text size="sm" c="dimmed">
              No findings.
            </Text>
          ) : (
            <ScrollArea h={440} type="auto">
              <Table striped fz="xs" stickyHeader>
                <Table.Thead>
                  <Table.Tr>
                    <Table.Th>Severity</Table.Th>
                    <Table.Th>Vulnerability</Table.Th>
                    <Table.Th>Package</Table.Th>
                    <Table.Th>Fixed in</Table.Th>
                  </Table.Tr>
                </Table.Thead>
                <Table.Tbody>
                  {data.findings.map((f) => (
                    <Table.Tr key={`${f.id}-${f.package}-${f.image}`}>
                      <Table.Td>
                        <Group gap={4} wrap="nowrap">
                          <SeverityBadge severity={f.severity} />
                          {f.kev && (
                            <Tooltip label="Known to be exploited (CISA KEV)">
                              <Badge color="red" size="xs" variant="filled">
                                KEV
                              </Badge>
                            </Tooltip>
                          )}
                        </Group>
                      </Table.Td>
                      <Table.Td>
                        {f.url ? (
                          <Anchor href={f.url} target="_blank" rel="noopener noreferrer" size="xs">
                            {f.id}
                          </Anchor>
                        ) : (
                          f.id
                        )}
                        {f.title && (
                          <Text size="xs" c="dimmed" lineClamp={1}>
                            {f.title}
                          </Text>
                        )}
                      </Table.Td>
                      <Table.Td>
                        {f.package} {f.version}
                      </Table.Td>
                      <Table.Td>
                        {f.fixed_in || (
                          <Text span size="xs" c="dimmed">
                            no fix yet
                          </Text>
                        )}
                      </Table.Td>
                    </Table.Tr>
                  ))}
                </Table.Tbody>
              </Table>
            </ScrollArea>
          )}
          {data.total > data.findings.length && (
            <Text size="xs" c="dimmed">
              Showing {data.findings.length} of {data.total}. See the rest in Coolify.
            </Text>
          )}
        </>
      )}
    </Stack>
  );
}
