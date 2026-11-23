"use client";

// The Coolify tool page: security across every team, for TAs and professors.
// Which deployed apps have security problems (Coolify's image scans), and which
// team servers have system updates waiting, with the fixes one click away.
// Details and everything else live on each team's Coolify panel.

import {
  Alert,
  Anchor,
  Badge,
  Button,
  Group,
  Loader,
  Modal,
  Skeleton,
  Stack,
  Table,
  Text,
  Title,
} from "@mantine/core";
import { notifications } from "@mantine/notifications";
import { IconAlertTriangle, IconRefresh, IconShieldCheck } from "@tabler/icons-react";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";

import { ToolKeys } from "@/components/ToolKeys";
import { ToolStatusAlert } from "@/components/ToolStatusAlert";
import { api } from "@/lib/api";
import { formatDateTime } from "@/lib/format";
import type {
  CoolifyActionResult,
  CoolifyAutoConnect,
  CoolifyResource,
  CoolifyServer,
  ServerJob,
  TeamSecurity,
} from "@/lib/types";
import { PatchSummary, SECURITY_RANK, SecurityBadge, errorMessage } from "@/modules/coolify/parts";

interface Confirm {
  title: string;
  body: string;
  run: () => Promise<void>;
}

export function CoolifyToolPage() {
  const [rows, setRows] = useState<TeamSecurity[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [version, setVersion] = useState(0);
  const [confirm, setConfirm] = useState<Confirm | null>(null);
  const [busy, setBusy] = useState(false);
  const [connecting, setConnecting] = useState(0);
  const [connectFailures, setConnectFailures] = useState<string[]>([]);

  useEffect(() => {
    api
      .get<TeamSecurity[]>("/tools/coolify/security")
      .then((r) => {
        setRows(r);
        setError(null);
      })
      .catch((err) => setError(errorMessage(err)));
  }, [version]);

  // Teams not connected yet, when the workbench can connect them itself: do it now,
  // one at a time, then reload. Once per visit, so a failing team doesn't loop.
  const autoTried = useRef(false);
  useEffect(() => {
    const pending = (rows ?? []).filter((t) => t.auto_connect && !t.token_set);
    if (autoTried.current || pending.length === 0) return;
    autoTried.current = true;
    (async () => {
      setConnecting(pending.length);
      const failed: string[] = [];
      for (const t of pending) {
        try {
          await api.post<CoolifyAutoConnect>(`/tools/coolify/teams/${t.team_id}/connect`);
        } catch (err) {
          failed.push(`${t.team_name}: ${errorMessage(err)}`);
        }
      }
      setConnecting(0);
      setConnectFailures(failed);
      setVersion((v) => v + 1);
    })();
  }, [rows]);

  const panel = (teamId: number) => `/teams/${teamId}/coolify`;

  async function redeploy(team: TeamSecurity, r: CoolifyResource) {
    try {
      const res = await api.post<CoolifyActionResult>(
        `/tools/coolify/teams/${team.team_id}/resources/${r.kind}/${r.uuid}/redeploy`,
      );
      notifications.show({
        color: "teal",
        title: `${team.team_name} · ${r.name}`,
        message: res.message,
      });
    } catch (err) {
      notifications.show({ color: "red", title: r.name, message: errorMessage(err) });
    }
  }

  async function startJob(team: TeamSecurity, s: CoolifyServer, kind: ServerJob["kind"]) {
    try {
      await api.post<ServerJob>(`/tools/coolify/teams/${team.team_id}/servers/${s.uuid}/jobs`, {
        kind,
      });
      notifications.show({
        color: "teal",
        title: `${team.team_name} · ${s.name}`,
        message: (
          <>
            Started. Follow it on the{" "}
            <Anchor component={Link} href={panel(team.team_id)} size="sm">
              team&apos;s Coolify page
            </Anchor>
            .
          </>
        ),
      });
      setTimeout(() => setVersion((v) => v + 1), 1500);
    } catch (err) {
      notifications.show({ color: "red", title: s.name, message: errorMessage(err) });
    }
  }

  const apps = (rows ?? [])
    .flatMap((t) => t.resources.map((r) => ({ team: t, r })))
    .sort(
      (a, b) =>
        (SECURITY_RANK[a.r.security?.status ?? "not_checked"] ?? 9) -
          (SECURITY_RANK[b.r.security?.status ?? "not_checked"] ?? 9) ||
        (b.r.security?.critical_count ?? 0) - (a.r.security?.critical_count ?? 0) ||
        a.team.team_name.localeCompare(b.team.team_name),
    );
  const servers = (rows ?? []).flatMap((t) => t.servers.map((s) => ({ team: t, s })));
  const noToken = (rows ?? []).filter((t) => !t.token_set);
  const failing = (rows ?? []).filter((t) => t.error);
  const urgent = apps.filter((a) => a.r.security?.status === "update_now").length;
  const serversWithSecurity = servers.filter(
    (x) => (x.s.last_patch_check?.result?.security_count ?? 0) > 0,
  ).length;

  return (
    <Stack gap="lg">
      <div>
        <Title order={2}>Coolify</Title>
        <Text c="dimmed">
          Security across every team: deployed apps with known vulnerabilities, and servers with
          system updates waiting. Open a team for logs, deployments, environment variables, and
          more.
        </Text>
      </div>
      <ToolStatusAlert toolId="coolify" />
      <ToolKeys toolId="coolify" />

      <Group justify="space-between">
        <Group gap="xs">
          <Title order={4}>Security across teams</Title>
          {rows && (
            <>
              <Badge color={urgent ? "red" : "teal"} variant="light">
                {urgent} app{urgent === 1 ? "" : "s"} to update now
              </Badge>
              <Badge color={serversWithSecurity ? "red" : "teal"} variant="light">
                {serversWithSecurity} server{serversWithSecurity === 1 ? "" : "s"} with security
                updates
              </Badge>
            </>
          )}
        </Group>
        <Button
          variant="default"
          size="xs"
          leftSection={<IconRefresh size={14} />}
          onClick={() => setVersion((v) => v + 1)}
        >
          Refresh
        </Button>
      </Group>

      {error && (
        <Alert color="red" icon={<IconAlertTriangle />}>
          {error}
        </Alert>
      )}
      {!rows && !error && <Skeleton h={200} />}

      {failing.map((t) => (
        <Alert key={t.team_id} color="orange" icon={<IconAlertTriangle />} p="xs">
          <b>{t.team_name}:</b> {t.error}
        </Alert>
      ))}
      {connecting > 0 && (
        <Alert color="blue" p="xs" icon={<Loader size={16} />}>
          Connecting {connecting} team{connecting === 1 ? "" : "s"} to Coolify automatically…
        </Alert>
      )}
      {connectFailures.length > 0 && (
        <Alert
          color="orange"
          icon={<IconAlertTriangle />}
          p="xs"
          title="Some teams couldn't connect"
        >
          {connectFailures.map((f) => (
            <Text key={f} size="sm">
              {f}
            </Text>
          ))}
        </Alert>
      )}
      {noToken.length > 0 && connecting === 0 && (
        <Text size="sm" c="dimmed">
          Not connected to Coolify yet (add your Coolify admin token in your API keys and they
          connect themselves, or open a team to paste its token):{" "}
          {noToken.map((t, i) => (
            <span key={t.team_id}>
              {i > 0 && ", "}
              <Anchor component={Link} href={panel(t.team_id)} size="sm">
                {t.team_name}
              </Anchor>
            </span>
          ))}
        </Text>
      )}

      {rows && (
        <Stack gap="xs">
          <Text fw={500}>Deployed apps</Text>
          {apps.length === 0 ? (
            <Text size="sm" c="dimmed">
              No scan results yet. Turn on automatic image scanning for a team&apos;s server on its
              page, or scan its containers from there.
            </Text>
          ) : (
            <Table.ScrollContainer minWidth={700}>
              <Table highlightOnHover verticalSpacing="xs">
                <Table.Thead>
                  <Table.Tr>
                    <Table.Th>Team</Table.Th>
                    <Table.Th>App</Table.Th>
                    <Table.Th>Security</Table.Th>
                    <Table.Th>What to do</Table.Th>
                    <Table.Th />
                  </Table.Tr>
                </Table.Thead>
                <Table.Tbody>
                  {apps.map(({ team, r }) => (
                    <Table.Tr key={`${team.team_id}-${r.uuid}`}>
                      <Table.Td>
                        <Anchor component={Link} href={panel(team.team_id)} size="sm">
                          {team.team_name}
                        </Anchor>
                      </Table.Td>
                      <Table.Td>
                        <Text size="sm">{r.name}</Text>
                      </Table.Td>
                      <Table.Td>
                        <SecurityBadge security={r.security} />
                      </Table.Td>
                      <Table.Td>
                        <Text size="xs" c="dimmed" maw={320}>
                          {r.security?.action}
                        </Text>
                      </Table.Td>
                      <Table.Td>
                        {(r.security?.status === "update_now" ||
                          r.security?.status === "update_available") && (
                          <Button
                            size="compact-xs"
                            variant="light"
                            color={r.security.status === "update_now" ? "red" : "orange"}
                            onClick={() =>
                              setConfirm({
                                title: `Redeploy ${r.name}?`,
                                body: `Rebuilds ${team.team_name}'s ${r.name} from scratch, pulling newer base images (the usual fix for “Update now”). If the problem is in the team's own code or dependencies, they'll need to fix it in their repository.`,
                                run: () => redeploy(team, r),
                              })
                            }
                          >
                            Redeploy
                          </Button>
                        )}
                      </Table.Td>
                    </Table.Tr>
                  ))}
                </Table.Tbody>
              </Table>
            </Table.ScrollContainer>
          )}
        </Stack>
      )}

      {rows && servers.length > 0 && (
        <Stack gap="xs">
          <Text fw={500}>Servers</Text>
          <Table.ScrollContainer minWidth={700}>
            <Table highlightOnHover verticalSpacing="xs">
              <Table.Thead>
                <Table.Tr>
                  <Table.Th>Team</Table.Th>
                  <Table.Th>Server</Table.Th>
                  <Table.Th>System updates</Table.Th>
                  <Table.Th />
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {servers.map(({ team, s }) => {
                  const check = s.last_patch_check;
                  const running = s.running_job?.status === "running";
                  return (
                    <Table.Tr key={`${team.team_id}-${s.uuid}`}>
                      <Table.Td>
                        <Anchor component={Link} href={panel(team.team_id)} size="sm">
                          {team.team_name}
                        </Anchor>
                      </Table.Td>
                      <Table.Td>
                        <Text size="sm">{s.name}</Text>
                        <Text size="xs" c="dimmed">
                          {s.ip}
                        </Text>
                      </Table.Td>
                      <Table.Td>
                        {running ? (
                          <Badge variant="light">Running…</Badge>
                        ) : check ? (
                          <Group gap={6}>
                            <PatchSummary job={check} />
                            <Text size="xs" c="dimmed">
                              {formatDateTime(check.finished_at ?? check.created_at)}
                            </Text>
                          </Group>
                        ) : (
                          <Text size="sm" c="dimmed">
                            not checked yet
                          </Text>
                        )}
                      </Table.Td>
                      <Table.Td>
                        <Group gap={4} justify="flex-end" wrap="nowrap">
                          <Button
                            size="compact-xs"
                            variant="default"
                            disabled={running}
                            onClick={() => startJob(team, s, "patch_check")}
                          >
                            Check
                          </Button>
                          {(check?.result?.security_count ?? 0) > 0 && (
                            <Button
                              size="compact-xs"
                              color="red"
                              variant="light"
                              leftSection={<IconShieldCheck size={12} />}
                              disabled={running}
                              onClick={() =>
                                setConfirm({
                                  title: `Install security updates on ${s.name}?`,
                                  body: `Installs ${check?.result?.security_count} security update(s) on ${team.team_name}'s server (${s.ip}). If Docker is updated, the team's containers restart briefly. The server is never rebooted automatically.`,
                                  run: () => startJob(team, s, "patch_security"),
                                })
                              }
                            >
                              Install security updates
                            </Button>
                          )}
                        </Group>
                      </Table.Td>
                    </Table.Tr>
                  );
                })}
              </Table.Tbody>
            </Table>
          </Table.ScrollContainer>
        </Stack>
      )}

      <Modal opened={confirm !== null} onClose={() => setConfirm(null)} title={confirm?.title}>
        <Stack>
          <Text size="sm">{confirm?.body}</Text>
          <Group justify="flex-end" gap="xs">
            <Button variant="default" onClick={() => setConfirm(null)}>
              Cancel
            </Button>
            <Button
              loading={busy}
              onClick={async () => {
                if (!confirm) return;
                setBusy(true);
                await confirm.run();
                setBusy(false);
                setConfirm(null);
              }}
            >
              Go ahead
            </Button>
          </Group>
        </Stack>
      </Modal>
    </Stack>
  );
}
