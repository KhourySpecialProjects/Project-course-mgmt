"use client";

// One team's Coolify, managed from the workbench with the team's own Coolify API
// token: its servers (update checks, security updates, container scans, Docker
// cleanup, automatic image scanning) and its apps, databases, and services
// (deploy, restart, stop, logs, deployments, environment variables, findings).

import {
  ActionIcon,
  Alert,
  Anchor,
  Button,
  Card,
  Group,
  Loader,
  Menu,
  Modal,
  PasswordInput,
  SimpleGrid,
  Skeleton,
  Stack,
  Switch,
  Table,
  Text,
  Title,
  Tooltip,
} from "@mantine/core";
import { notifications } from "@mantine/notifications";
import {
  IconAlertTriangle,
  IconArrowLeft,
  IconBrush,
  IconChevronDown,
  IconDots,
  IconExternalLink,
  IconFileText,
  IconHistory,
  IconKey,
  IconPlayerPlay,
  IconPlayerStop,
  IconRefresh,
  IconRotateClockwise,
  IconScan,
  IconShieldCheck,
  IconShieldExclamation,
  IconVariable,
} from "@tabler/icons-react";
import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";

import { useAuth } from "@/components/AuthProvider";
import { api } from "@/lib/api";
import { formatDateTime } from "@/lib/format";
import { apiKeysPath } from "@/lib/paths";
import type {
  CoolifyAction,
  CoolifyActionResult,
  CoolifyAutoConnect,
  CoolifyOverview,
  CoolifyResource,
  CoolifyServer,
  CredentialStatus,
  ServerJob,
  ServerJobKind,
} from "@/lib/types";
import { ApiConsole } from "@/modules/coolify/ApiConsole";
import {
  DeploymentsDialog,
  EnvDialog,
  FindingsDialog,
  LogsDialog,
} from "@/modules/coolify/dialogs";
import {
  JOB_LABELS,
  JobDetails,
  JobStatusBadge,
  PatchSummary,
  ResourceStatus,
  SECURITY_RANK,
  SecurityBadge,
  errorMessage,
  useJob,
} from "@/modules/coolify/parts";

const TOKEN_KEY = "coolify_team_token";

type View = "logs" | "deployments" | "env" | "findings";

interface Confirm {
  title: string;
  body: string;
  label: string;
  color?: string;
  run: () => Promise<void>;
}

export function CoolifyTeamPanel({
  teamId,
  embedded = false,
}: {
  teamId: number;
  /** Shown inside the team's page: leave out the page title. */
  embedded?: boolean;
}) {
  const [data, setData] = useState<CoolifyOverview | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [version, setVersion] = useState(0);
  const [view, setView] = useState<{ kind: View; resource: CoolifyResource } | null>(null);
  const [confirm, setConfirm] = useState<Confirm | null>(null);
  const [confirming, setConfirming] = useState(false);
  const reload = useCallback(() => setVersion((v) => v + 1), []);

  useEffect(() => {
    let cancelled = false;
    api
      .get<CoolifyOverview>(`/tools/coolify/teams/${teamId}/overview`)
      .then((d) => {
        if (!cancelled) {
          setData(d);
          setLoadError(null);
        }
      })
      .catch((err) => !cancelled && setLoadError(errorMessage(err)));
    return () => {
      cancelled = true;
    };
  }, [teamId, version]);

  async function act(resource: CoolifyResource, action: CoolifyAction) {
    try {
      const r = await api.post<CoolifyActionResult>(
        `/tools/coolify/teams/${teamId}/resources/${resource.kind}/${resource.uuid}/${action}`,
      );
      notifications.show({ color: "teal", title: resource.name, message: r.message });
      setTimeout(reload, 3000);
    } catch (err) {
      notifications.show({ color: "red", title: resource.name, message: errorMessage(err) });
    }
  }

  function ask(resource: CoolifyResource, action: CoolifyAction) {
    const what = {
      redeploy: {
        title: `Redeploy ${resource.name}?`,
        body:
          resource.kind === "applications"
            ? "Rebuilds the app from its repository from scratch, pulling newer base images. This is the usual fix for “Update now”. The app keeps running until the new build is ready."
            : resource.kind === "services"
              ? "Pulls the latest images and restarts the service."
              : "Restarts the database.",
        label: "Redeploy",
      },
      stop: {
        title: `Stop ${resource.name}?`,
        body: "It will be offline until it's started again.",
        label: "Stop",
        color: "red",
      },
      restart: {
        title: `Restart ${resource.name}?`,
        body: "It will blip briefly.",
        label: "Restart",
      },
      start: {
        title: `Start ${resource.name}?`,
        body: resource.kind === "applications" ? "Deploys it." : "Starts it.",
        label: "Start",
      },
    }[action];
    setConfirm({ ...what, run: () => act(resource, action) });
  }

  if (loadError) {
    return (
      <Alert color="red" icon={<IconAlertTriangle />} title="Couldn't load this team">
        {loadError}
      </Alert>
    );
  }
  if (!data) return <Skeleton h={300} />;

  const resources = [...data.resources].sort(
    (a, b) =>
      (SECURITY_RANK[a.security?.status ?? "not_checked"] ?? 9) -
        (SECURITY_RANK[b.security?.status ?? "not_checked"] ?? 9) || a.name.localeCompare(b.name),
  );
  const viewTitle = view
    ? {
        logs: `Logs · ${view.resource.name}`,
        deployments: `Deployments · ${view.resource.name}`,
        env: `Environment variables · ${view.resource.name}`,
        findings: `Security findings · ${view.resource.name}`,
      }[view.kind]
    : "";

  return (
    <Stack gap="lg">
      <Group justify="space-between" align="flex-start">
        <div>
          {!embedded && (
            <>
              <Anchor component={Link} href={`/teams/${teamId}`} size="sm" c="dimmed">
                <Group gap={4}>
                  <IconArrowLeft size={14} /> {data.team_name}
                </Group>
              </Anchor>
              <Title order={2}>{data.team_name} · Coolify</Title>
            </>
          )}
          <Text c="dimmed" size="sm">
            {data.coolify_team
              ? `Coolify team: ${data.coolify_team}`
              : "Everything here uses this team's own Coolify API token."}
          </Text>
        </div>
        <Group gap="xs">
          <Button variant="default" leftSection={<IconRefresh size={16} />} onClick={reload}>
            Refresh
          </Button>
          {data.dashboard_url && (
            <Button
              component="a"
              href={data.dashboard_url}
              target="_blank"
              rel="noopener noreferrer"
              variant="light"
              rightSection={<IconExternalLink size={14} />}
            >
              Open Coolify
            </Button>
          )}
        </Group>
      </Group>

      <TokenCard
        teamId={teamId}
        teamName={data.team_name}
        tokenSet={data.token_set}
        autoConnect={data.auto_connect}
        onChange={reload}
      />

      {data.error && (
        <Alert color="red" icon={<IconAlertTriangle />} title="Coolify couldn't be reached">
          {data.error}
        </Alert>
      )}

      {data.token_set && !data.error && (
        <>
          <Stack gap="sm">
            <Title order={4}>Servers</Title>
            {data.servers.length === 0 ? (
              <Text size="sm" c="dimmed">
                This Coolify team has no servers.
              </Text>
            ) : (
              <SimpleGrid cols={{ base: 1, md: 2 }}>
                {data.servers.map((s) => (
                  <ServerCard
                    key={s.uuid}
                    teamId={teamId}
                    server={s}
                    onChange={reload}
                    onConfirm={setConfirm}
                  />
                ))}
              </SimpleGrid>
            )}
          </Stack>

          <Stack gap="sm">
            <Group justify="space-between">
              <Title order={4}>Apps, databases, and services</Title>
              {data.security_error && (
                <Tooltip label={data.security_error} multiline maw={360}>
                  <Text size="xs" c="orange">
                    Security results unavailable
                  </Text>
                </Tooltip>
              )}
            </Group>
            {resources.length === 0 ? (
              <Text size="sm" c="dimmed">
                Nothing deployed yet.
              </Text>
            ) : (
              <Table.ScrollContainer minWidth={760}>
                <Table highlightOnHover verticalSpacing="sm">
                  <Table.Thead>
                    <Table.Tr>
                      <Table.Th>Name</Table.Th>
                      <Table.Th>Where</Table.Th>
                      <Table.Th>Status</Table.Th>
                      <Table.Th>Security</Table.Th>
                      <Table.Th />
                    </Table.Tr>
                  </Table.Thead>
                  <Table.Tbody>
                    {resources.map((r) => (
                      <ResourceRow
                        key={r.uuid}
                        resource={r}
                        onAsk={(action) => ask(r, action)}
                        onView={(kind) => setView({ kind, resource: r })}
                      />
                    ))}
                  </Table.Tbody>
                </Table>
              </Table.ScrollContainer>
            )}
          </Stack>

          <ApiConsole teamId={teamId} resources={data.resources} servers={data.servers} />
        </>
      )}

      <Modal opened={view !== null} onClose={() => setView(null)} title={viewTitle} size="xl">
        {view?.kind === "logs" && <LogsDialog teamId={teamId} resource={view.resource} />}
        {view?.kind === "deployments" && (
          <DeploymentsDialog teamId={teamId} resource={view.resource} />
        )}
        {view?.kind === "env" && <EnvDialog teamId={teamId} resource={view.resource} />}
        {view?.kind === "findings" && <FindingsDialog teamId={teamId} resource={view.resource} />}
      </Modal>

      <Modal opened={confirm !== null} onClose={() => setConfirm(null)} title={confirm?.title}>
        <Stack>
          <Text size="sm">{confirm?.body}</Text>
          <Group justify="flex-end" gap="xs">
            <Button variant="default" onClick={() => setConfirm(null)}>
              Cancel
            </Button>
            <Button
              color={confirm?.color}
              loading={confirming}
              onClick={async () => {
                if (!confirm) return;
                setConfirming(true);
                await confirm.run();
                setConfirming(false);
                setConfirm(null);
              }}
            >
              {confirm?.label}
            </Button>
          </Group>
        </Stack>
      </Modal>
    </Stack>
  );
}

// --- The team's token ------------------------------------------------------------

function TokenCard({
  teamId,
  teamName,
  tokenSet,
  autoConnect,
  onChange,
}: {
  teamId: number;
  teamName: string;
  tokenSet: boolean;
  /** The workbench can make the team's token itself: do it as soon as the page opens. */
  autoConnect: boolean;
  onChange: () => void;
}) {
  const { user } = useAuth();
  const [status, setStatus] = useState<CredentialStatus | null>(null);
  const [editing, setEditing] = useState(false);
  const [value, setValue] = useState("");
  const [saving, setSaving] = useState(false);
  const [connecting, setConnecting] = useState(!tokenSet && autoConnect);
  const [connectError, setConnectError] = useState<string | null>(null);
  const started = useRef(false);

  const connect = useCallback(() => {
    setConnecting(true);
    setConnectError(null);
    api
      .post<CoolifyAutoConnect>(`/tools/coolify/teams/${teamId}/connect`)
      .then((r) => {
        notifications.show({ color: "teal", message: r.message });
        onChange();
      })
      .catch((err) => setConnectError(errorMessage(err)))
      .finally(() => setConnecting(false));
  }, [teamId, onChange]);

  // No token yet, but the workbench can make one: connect right away, once.
  useEffect(() => {
    if (tokenSet || !autoConnect || started.current) return;
    started.current = true;
    api
      .post<CoolifyAutoConnect>(`/tools/coolify/teams/${teamId}/connect`)
      .then((r) => {
        notifications.show({ color: "teal", message: r.message });
        onChange();
      })
      .catch((err) => setConnectError(errorMessage(err)))
      .finally(() => setConnecting(false));
  }, [teamId, tokenSet, autoConnect, onChange]);

  useEffect(() => {
    api
      .get<CredentialStatus[]>(`/teams/${teamId}/credentials`)
      .then((list) => setStatus(list.find((c) => c.key === TOKEN_KEY) ?? null))
      .catch(() => setStatus(null));
  }, [teamId, tokenSet]);

  async function save() {
    setSaving(true);
    try {
      await api.put(`/teams/${teamId}/credentials/${TOKEN_KEY}`, { value });
      setValue("");
      setEditing(false);
      notifications.show({ color: "teal", message: "Saved this team's Coolify API token" });
      onChange();
    } catch (err) {
      notifications.show({ color: "red", message: errorMessage(err) });
    } finally {
      setSaving(false);
    }
  }

  async function remove() {
    try {
      await api.delete(`/teams/${teamId}/credentials/${TOKEN_KEY}`);
      notifications.show({ message: "Removed this team's Coolify API token" });
      onChange();
    } catch (err) {
      notifications.show({ color: "red", message: errorMessage(err) });
    }
  }

  const form = (
    <Group align="flex-end" gap="xs" wrap="nowrap">
      <PasswordInput
        label="Coolify API token"
        placeholder={status?.placeholder || "1|..."}
        value={value}
        onChange={(e) => setValue(e.currentTarget.value)}
        style={{ flex: 1 }}
      />
      <Button onClick={save} loading={saving} disabled={!value.trim()}>
        Save
      </Button>
      {tokenSet && (
        <Button variant="default" onClick={() => setEditing(false)}>
          Cancel
        </Button>
      )}
    </Group>
  );

  if (!tokenSet && connecting) {
    return (
      <Card withBorder>
        <Group gap="sm">
          <Loader size="sm" />
          <Text size="sm">
            Connecting {teamName} to its Coolify team automatically (creating its own token on the
            Coolify server)…
          </Text>
        </Group>
      </Card>
    );
  }

  if (!tokenSet) {
    return (
      <Card withBorder>
        <Stack gap="sm">
          <Group gap="xs">
            <IconKey size={18} />
            <Text fw={600}>Connect this team&apos;s Coolify</Text>
          </Group>
          {connectError ? (
            <Alert color="red" icon={<IconAlertTriangle />} title="Couldn't connect automatically">
              <Text size="sm">{connectError}</Text>
              <Button size="xs" mt="sm" variant="white" onClick={connect}>
                Try again
              </Button>
            </Alert>
          ) : (
            <Text size="sm">
              Teams connect themselves once you add your <b>Coolify admin token</b> (a token from
              your main Coolify team, with the root permission) in{" "}
              <Anchor component={Link} href={apiKeysPath(user)} size="sm">
                your API keys
              </Anchor>
              . Coolify&apos;s API must be on: <b>Settings → Advanced → API and MCP</b>.
            </Text>
          )}
          <Text size="xs" c="dimmed">
            Or paste one by hand: in Coolify, switch to this team, open{" "}
            <b>Keys &amp; Tokens → API tokens</b>, and create a token with read, read:sensitive,
            write, and deploy.
          </Text>
          {form}
        </Stack>
      </Card>
    );
  }

  return (
    <Card withBorder py="xs">
      {editing ? (
        form
      ) : (
        <Group justify="space-between">
          <Group gap="xs">
            <IconKey size={16} />
            <Text size="sm">
              Coolify API token saved{status?.hint ? ` (ends in …${status.hint})` : ""}
              {status?.updated_at ? ` · ${formatDateTime(status.updated_at)}` : ""}
            </Text>
          </Group>
          <Group gap="xs">
            <Button size="compact-sm" variant="default" onClick={() => setEditing(true)}>
              Replace
            </Button>
            <Button size="compact-sm" variant="subtle" color="red" onClick={remove}>
              Remove
            </Button>
          </Group>
        </Group>
      )}
    </Card>
  );
}

// --- A server ----------------------------------------------------------------------

function ServerCard({
  teamId,
  server,
  onChange,
  onConfirm,
}: {
  teamId: number;
  server: CoolifyServer;
  onChange: () => void;
  onConfirm: (c: Confirm) => void;
}) {
  const base = `/tools/coolify/teams/${teamId}/servers/${server.uuid}`;
  const [job, setJob] = useState<ServerJob | null>(server.running_job);
  const [shownJob, setShownJob] = useState<ServerJob | null>(null);
  const [scanning, setScanning] = useState(server.image_scanning);
  const check = server.last_patch_check;
  const securityCount = check?.result?.security_count ?? 0;

  async function start(kind: ServerJobKind) {
    try {
      setJob(await api.post<ServerJob>(`${base}/jobs`, { kind }));
    } catch (err) {
      notifications.show({ color: "red", title: server.name, message: errorMessage(err) });
    }
  }

  function confirmPatch(kind: "patch_security" | "patch_all") {
    onConfirm({
      title: kind === "patch_security" ? "Install security updates?" : "Install all updates?",
      body: `Installs ${kind === "patch_security" ? "the security updates" : "every available update"} on ${server.name} (${server.ip}) with apt. If Docker is updated, this team's containers restart and their apps blip briefly. The server is never rebooted automatically; you'll see if it needs one.`,
      label: "Install",
      run: () => start(kind),
    });
  }

  async function toggleScanning(enabled: boolean) {
    setScanning(enabled);
    try {
      await api.put(`${base}/image-scanning`, { enabled });
      notifications.show({
        message: enabled
          ? "Automatic image scanning is on: Coolify scans after each deploy and daily."
          : "Automatic image scanning is off.",
      });
    } catch (err) {
      setScanning(!enabled);
      notifications.show({ color: "red", message: errorMessage(err) });
    }
  }

  async function cleanup() {
    try {
      const r = await api.post<CoolifyActionResult>(`${base}/docker-cleanup`);
      notifications.show({ color: "teal", title: server.name, message: r.message });
    } catch (err) {
      notifications.show({ color: "red", title: server.name, message: errorMessage(err) });
    }
  }

  return (
    <Card withBorder>
      <Stack gap="sm">
        <Group justify="space-between" align="flex-start">
          <div>
            <Text fw={600}>{server.name}</Text>
            <Text size="sm" c="dimmed">
              {server.ip}
              {server.reachable === false
                ? " · not reachable"
                : server.reachable
                  ? " · reachable"
                  : ""}
            </Text>
          </div>
          {scanning !== null && (
            <Tooltip
              label="Coolify scans container images after each deploy and once a day"
              multiline
              maw={260}
            >
              <div>
                <Switch
                  size="sm"
                  label="Auto image scans"
                  checked={scanning}
                  onChange={(e) => toggleScanning(e.currentTarget.checked)}
                />
              </div>
            </Tooltip>
          )}
        </Group>

        <Group gap="xs">
          <Text size="sm" fw={500}>
            System updates:
          </Text>
          {check ? (
            <>
              <PatchSummary job={check} />
              <Text size="xs" c="dimmed">
                checked {formatDateTime(check.finished_at ?? check.created_at)}
              </Text>
            </>
          ) : (
            <Text size="sm" c="dimmed">
              not checked yet
            </Text>
          )}
        </Group>

        {server.last_image_scan?.result?.images && (
          <Group gap="xs">
            <Text size="sm" fw={500}>
              Last container scan:
            </Text>
            <Text size="sm">
              {server.last_image_scan.result.images.reduce(
                (n, i) => n + (i.counts?.critical ?? 0),
                0,
              )}{" "}
              critical,{" "}
              {server.last_image_scan.result.images.reduce((n, i) => n + (i.counts?.high ?? 0), 0)}{" "}
              high
            </Text>
            <Anchor
              size="xs"
              component="button"
              onClick={() => setShownJob(server.last_image_scan)}
            >
              details
            </Anchor>
          </Group>
        )}

        {job && <RunningJob teamId={teamId} job={job} onDone={onChange} onOpen={setShownJob} />}

        <Group gap="xs">
          <Button
            size="xs"
            variant="default"
            leftSection={<IconRefresh size={14} />}
            disabled={job?.status === "running"}
            onClick={() => start("patch_check")}
          >
            Check for updates
          </Button>
          <Button.Group>
            <Button
              size="xs"
              color={securityCount ? "red" : undefined}
              leftSection={<IconShieldCheck size={14} />}
              disabled={job?.status === "running"}
              onClick={() => confirmPatch("patch_security")}
            >
              Install security updates{securityCount ? ` (${securityCount})` : ""}
            </Button>
            <Menu position="bottom-end" withinPortal>
              <Menu.Target>
                <Button
                  size="xs"
                  color={securityCount ? "red" : undefined}
                  px={6}
                  disabled={job?.status === "running"}
                  aria-label="More server actions"
                >
                  <IconChevronDown size={14} />
                </Button>
              </Menu.Target>
              <Menu.Dropdown>
                <Menu.Item onClick={() => confirmPatch("patch_all")}>Install all updates</Menu.Item>
                <Menu.Item leftSection={<IconScan size={14} />} onClick={() => start("image_scan")}>
                  Scan containers now
                </Menu.Item>
                <Menu.Item leftSection={<IconBrush size={14} />} onClick={cleanup}>
                  Docker cleanup
                </Menu.Item>
                {check && (
                  <Menu.Item
                    leftSection={<IconFileText size={14} />}
                    onClick={() => setShownJob(check)}
                  >
                    Last update check details
                  </Menu.Item>
                )}
              </Menu.Dropdown>
            </Menu>
          </Button.Group>
        </Group>
      </Stack>

      <Modal
        opened={shownJob !== null}
        onClose={() => setShownJob(null)}
        title={server.name}
        size="lg"
      >
        {shownJob && <JobDetails job={shownJob} />}
      </Modal>
    </Card>
  );
}

function RunningJob({
  teamId,
  job: initial,
  onDone,
  onOpen,
}: {
  teamId: number;
  job: ServerJob;
  onDone: () => void;
  onOpen: (job: ServerJob) => void;
}) {
  const job = useJob(teamId, initial, onDone);
  const lastLine = job.log.trim().split("\n").pop();
  return (
    <Alert
      color={job.status === "failed" ? "red" : job.status === "succeeded" ? "teal" : "blue"}
      p="xs"
    >
      <Group justify="space-between" wrap="nowrap">
        <Group gap="xs" wrap="nowrap" style={{ minWidth: 0 }}>
          <JobStatusBadge job={job} />
          <Text size="sm" fw={500}>
            {JOB_LABELS[job.kind]}
          </Text>
          <Text size="xs" c="dimmed" truncate>
            {job.error || lastLine}
          </Text>
        </Group>
        <Anchor size="xs" component="button" onClick={() => onOpen(job)}>
          {job.status === "running" ? "follow" : "details"}
        </Anchor>
      </Group>
    </Alert>
  );
}

// --- An app, database, or service ----------------------------------------------------

function ResourceRow({
  resource: r,
  onAsk,
  onView,
}: {
  resource: CoolifyResource;
  onAsk: (action: CoolifyAction) => void;
  onView: (view: View) => void;
}) {
  const isApp = r.kind === "applications";
  const running = r.status.startsWith("running");
  const urgent = r.security?.status === "update_now";
  return (
    <Table.Tr>
      <Table.Td>
        <Text size="sm" fw={500}>
          {r.name}
        </Text>
        <Text size="xs" c="dimmed">
          {{ applications: "App", databases: "Database", services: "Service" }[r.kind]}
          {r.fqdn && (
            <>
              {" · "}
              <Anchor
                href={r.fqdn.split(",")[0]}
                target="_blank"
                rel="noopener noreferrer"
                size="xs"
              >
                {r.fqdn.split(",")[0].replace(/^https?:\/\//, "")}
              </Anchor>
            </>
          )}
        </Text>
      </Table.Td>
      <Table.Td>
        <Text size="sm">{[r.project, r.environment].filter(Boolean).join(" / ") || "—"}</Text>
      </Table.Td>
      <Table.Td>
        <ResourceStatus status={r.status} />
      </Table.Td>
      <Table.Td>
        {r.security ? (
          <Anchor component="button" onClick={() => onView("findings")}>
            <SecurityBadge security={r.security} />
          </Anchor>
        ) : (
          <SecurityBadge security={null} />
        )}
      </Table.Td>
      <Table.Td>
        <Group gap={4} justify="flex-end" wrap="nowrap">
          {urgent && (
            <Button
              size="compact-xs"
              color="red"
              variant="light"
              leftSection={<IconShieldExclamation size={12} />}
              onClick={() => onAsk("redeploy")}
            >
              Update now
            </Button>
          )}
          <Menu position="bottom-end" withinPortal>
            <Menu.Target>
              <ActionIcon variant="subtle" color="gray" aria-label={`Actions for ${r.name}`}>
                <IconDots size={16} />
              </ActionIcon>
            </Menu.Target>
            <Menu.Dropdown>
              <Menu.Item
                leftSection={<IconRotateClockwise size={14} />}
                onClick={() => onAsk("redeploy")}
              >
                {isApp
                  ? "Redeploy (fresh build)"
                  : r.kind === "services"
                    ? "Pull latest & restart"
                    : "Redeploy"}
              </Menu.Item>
              <Menu.Item leftSection={<IconRefresh size={14} />} onClick={() => onAsk("restart")}>
                Restart
              </Menu.Item>
              {running ? (
                <Menu.Item
                  color="red"
                  leftSection={<IconPlayerStop size={14} />}
                  onClick={() => onAsk("stop")}
                >
                  Stop
                </Menu.Item>
              ) : (
                <Menu.Item
                  leftSection={<IconPlayerPlay size={14} />}
                  onClick={() => onAsk("start")}
                >
                  Start
                </Menu.Item>
              )}
              <Menu.Divider />
              {isApp && (
                <>
                  <Menu.Item
                    leftSection={<IconFileText size={14} />}
                    onClick={() => onView("logs")}
                  >
                    Logs
                  </Menu.Item>
                  <Menu.Item
                    leftSection={<IconHistory size={14} />}
                    onClick={() => onView("deployments")}
                  >
                    Deployments
                  </Menu.Item>
                  <Menu.Item leftSection={<IconVariable size={14} />} onClick={() => onView("env")}>
                    Environment variables
                  </Menu.Item>
                </>
              )}
              <Menu.Item
                leftSection={<IconShieldCheck size={14} />}
                onClick={() => onView("findings")}
              >
                Security findings
              </Menu.Item>
            </Menu.Dropdown>
          </Menu>
        </Group>
      </Table.Td>
    </Table.Tr>
  );
}
