"use client";

// One team on the dashboard:
//
//   Team Alpha                                         [...]
//   [GitHub] [Linear] [Coolify] [Figma] ...
//
// Each built-in service (any API tool module with a `team_service`) gets a button.
// A solid button opens the team's repo/team/server. A dashed one means it hasn't
// been set up yet: clicking it offers to create (or find) it. Custom links come
// after. "Find links" in the menu links everything that already exists.

import { ActionIcon, Button, Card, Group, Menu, Modal, Text, Tooltip } from "@mantine/core";
import { notifications } from "@mantine/notifications";
import {
  IconDots,
  IconExternalLink,
  IconLink,
  IconLinkPlus,
  IconPencil,
  IconPlus,
  IconSearch,
  IconTrash,
} from "@tabler/icons-react";
import Link from "next/link";
import { useState } from "react";

import {
  CreateServiceDialog,
  DeleteTeamDialog,
  EditLinksDialog,
  LinkForm,
  type LinkValues,
  TeamNameForm,
} from "@/components/teams/TeamDialogs";
import { api } from "@/lib/api";
import type { Team, TeamConnected, TeamLink, TeamService } from "@/lib/types";
import { connectCoolifyInBackground } from "@/modules/coolify/parts";
import { ToolIcon, teamPanelHref } from "@/modules/registry";

type Dialog =
  | { kind: "rename" }
  | { kind: "add-link" }
  | { kind: "edit-links" }
  | { kind: "delete" }
  | { kind: "create"; service: TeamService };

interface Props {
  team: Team;
  services: TeamService[];
  onChange: (team: Team) => void;
  onDeleted: (teamId: number) => void;
}

export function TeamCard({ team, services, onChange, onDeleted }: Props) {
  const [dialog, setDialog] = useState<Dialog | null>(null);
  const close = () => setDialog(null);

  const serviceIds = new Set(services.map((s) => s.id));
  // Links for services that aren't installed any more are shown like custom links.
  const otherLinks = team.links.filter((l) => !l.service_id || !serviceIds.has(l.service_id));

  async function rename(name: string) {
    onChange(await api.patch<Team>(`/teams/${team.id}`, { name }));
    close();
  }

  async function addLink(values: LinkValues) {
    onChange(await api.post<Team>(`/teams/${team.id}/links`, values));
    notifications.show({ message: `Added ${values.label} to ${team.name}` });
    close();
  }

  function done(updated: Team) {
    onChange(updated);
    close();
  }

  // Link whatever already exists for the team in each service. Creates nothing.
  async function findLinks() {
    const id = notifications.show({
      loading: true,
      autoClose: false,
      withCloseButton: false,
      title: team.name,
      message: `Looking for ${team.name}'s links...`,
    });
    try {
      const result = await api.post<TeamConnected>(`/teams/${team.id}/connect`);
      onChange(result.team);
      if (result.results.some((r) => r.service_id === "coolify" && r.outcome === "linked")) {
        connectCoolifyInBackground(team.id);
      }
      const name = (serviceId: string) =>
        services.find((s) => s.id === serviceId)?.name ?? serviceId;
      const linked = result.results.filter((r) => r.outcome === "linked");
      const problems = result.results.filter(
        (r) => r.outcome !== "linked" && r.outcome !== "already_linked",
      );
      notifications.update({
        id,
        loading: false,
        autoClose: problems.length > 0 ? false : 6000,
        withCloseButton: true,
        color: linked.length > 0 ? "teal" : problems.length > 0 ? "yellow" : "gray",
        title: linked.length > 0 ? `Linked ${linked.length} for ${team.name}` : team.name,
        message: (
          <>
            {result.results
              .filter((r) => r.outcome !== "already_linked")
              .map((r) => (
                <Text key={r.service_id} size="sm">
                  <b>{name(r.service_id)}:</b> {r.message}
                </Text>
              ))}
            {linked.length === 0 && problems.length === 0 && (
              <Text size="sm">Everything is already linked.</Text>
            )}
          </>
        ),
      });
    } catch (err) {
      notifications.update({
        id,
        loading: false,
        autoClose: false,
        withCloseButton: true,
        color: "red",
        title: team.name,
        message: err instanceof Error ? err.message : String(err),
      });
    }
  }

  const missingService = services.some((s) => !team.links.some((l) => l.service_id === s.id));

  const createService = dialog?.kind === "create" ? dialog.service : null;

  return (
    <Card withBorder padding="md">
      <Group justify="space-between" wrap="nowrap" gap="xs" mb="sm">
        <Text fw={600} truncate title={team.name}>
          {team.name}
        </Text>
        <Menu position="bottom-end" withinPortal>
          <Menu.Target>
            <ActionIcon variant="subtle" color="gray" aria-label={`Actions for ${team.name}`}>
              <IconDots size={18} />
            </ActionIcon>
          </Menu.Target>
          <Menu.Dropdown>
            {services
              .filter((s) => teamPanelHref(s.id, team.id))
              .map((s) => (
                <Menu.Item
                  key={s.id}
                  component={Link}
                  href={teamPanelHref(s.id, team.id) ?? "#"}
                  leftSection={<ToolIcon toolId={s.id} size={14} />}
                >
                  Open {s.name} panel
                </Menu.Item>
              ))}
            {missingService && (
              <Menu.Item leftSection={<IconSearch size={14} />} onClick={findLinks}>
                Find links
              </Menu.Item>
            )}
            <Menu.Item
              leftSection={<IconPencil size={14} />}
              onClick={() => setDialog({ kind: "rename" })}
            >
              Rename
            </Menu.Item>
            <Menu.Item
              leftSection={<IconLinkPlus size={14} />}
              onClick={() => setDialog({ kind: "add-link" })}
            >
              Add link
            </Menu.Item>
            {team.links.length > 0 && (
              <Menu.Item
                leftSection={<IconLink size={14} />}
                onClick={() => setDialog({ kind: "edit-links" })}
              >
                Edit links
              </Menu.Item>
            )}
            <Menu.Divider />
            <Menu.Item
              color="red"
              leftSection={<IconTrash size={14} />}
              onClick={() => setDialog({ kind: "delete" })}
            >
              Delete team
            </Menu.Item>
          </Menu.Dropdown>
        </Menu>
      </Group>

      <Group gap="xs">
        {services.map((s) => (
          <ServiceButton
            key={s.id}
            service={s}
            link={team.links.find((l) => l.service_id === s.id)}
            panelHref={teamPanelHref(s.id, team.id)}
            onCreate={() => setDialog({ kind: "create", service: s })}
          />
        ))}
        {otherLinks.map((l) => (
          <Button
            key={l.id}
            component="a"
            href={l.url}
            target="_blank"
            rel="noopener noreferrer"
            size="xs"
            variant="light"
            color="gray"
            leftSection={<IconLink size={14} />}
            rightSection={<IconExternalLink size={12} />}
          >
            {l.label}
          </Button>
        ))}
      </Group>

      <Modal opened={dialog?.kind === "rename"} onClose={close} title="Rename team">
        <TeamNameForm initialName={team.name} submitLabel="Save" onSubmit={rename} />
      </Modal>

      <Modal
        opened={dialog?.kind === "add-link"}
        onClose={close}
        title={`Add a link to ${team.name}`}
      >
        <Text size="sm" c="dimmed" mb="sm">
          Any other service the team uses: a Figma file, a Slack channel, a docs site, ...
        </Text>
        <LinkForm submitLabel="Add link" onSubmit={addLink} />
      </Modal>

      <Modal
        opened={dialog?.kind === "edit-links"}
        onClose={close}
        title={`${team.name}'s links`}
        size="lg"
      >
        <EditLinksDialog team={team} services={services} onChange={onChange} />
      </Modal>

      <Modal
        opened={createService !== null}
        onClose={close}
        title={createService ? `${createService.name} for ${team.name}` : ""}
      >
        {createService && <CreateServiceDialog team={team} service={createService} onDone={done} />}
      </Modal>

      <Modal opened={dialog?.kind === "delete"} onClose={close} title="Delete team">
        <DeleteTeamDialog team={team} onCancel={close} onDeleted={() => onDeleted(team.id)} />
      </Modal>
    </Card>
  );
}

function ServiceButton({
  service,
  link,
  panelHref,
  onCreate,
}: {
  service: TeamService;
  link: TeamLink | undefined;
  /** The team's page for this tool (e.g. its Coolify panel), opened instead of the link. */
  panelHref: string | null;
  onCreate: () => void;
}) {
  const icon = <ToolIcon toolId={service.id} size={14} />;

  if (link && panelHref) {
    return (
      <Tooltip label={`${link.label} · open the team's ${service.name} panel`} withArrow>
        <Button component={Link} href={panelHref} size="xs" variant="light" leftSection={icon}>
          {service.name}
        </Button>
      </Tooltip>
    );
  }

  if (link) {
    return (
      // The label says what it points to, e.g. "org/repo" or "BeforeDawn · 167.99.6.42".
      <Tooltip label={link.label} withArrow disabled={link.label === service.name}>
        <Button
          component="a"
          href={link.url}
          target="_blank"
          rel="noopener noreferrer"
          size="xs"
          variant="light"
          leftSection={icon}
          rightSection={<IconExternalLink size={12} />}
        >
          {service.name}
        </Button>
      </Tooltip>
    );
  }

  return (
    <Tooltip
      label={`${service.can_create ? "Create" : "Find"} this team's ${service.name} ${service.resource_name}`}
      withArrow
    >
      <Button
        size="xs"
        variant="default"
        leftSection={icon}
        rightSection={<IconPlus size={12} />}
        style={{ borderStyle: "dashed" }}
        onClick={onCreate}
      >
        {service.name}
      </Button>
    </Tooltip>
  );
}
