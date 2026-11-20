"use client";

// The dashboard's Teams section: an "Add team" button and one card per student
// team (see TeamCard). Teams and their links come from GET /api/teams; which
// service buttons each card gets comes from GET /api/teams/services.

import {
  Button,
  Card,
  Group,
  Modal,
  SimpleGrid,
  Skeleton,
  Stack,
  Text,
  Title,
} from "@mantine/core";
import { notifications } from "@mantine/notifications";
import { IconPlus, IconUsersGroup } from "@tabler/icons-react";
import { useEffect, useState } from "react";

import { AddTeamDialog } from "@/components/teams/AddTeamDialog";
import { TeamCard } from "@/components/teams/TeamCard";
import { api } from "@/lib/api";
import type { Team, TeamService } from "@/lib/types";

// "Team 2" before "Team 10", ignoring case.
const byName = (a: Team, b: Team) =>
  a.name.localeCompare(b.name, undefined, { numeric: true, sensitivity: "base" });

export function TeamsSection() {
  const [teams, setTeams] = useState<Team[] | null>(null);
  const [services, setServices] = useState<TeamService[]>([]);
  const [adding, setAdding] = useState(false);

  useEffect(() => {
    api
      .get<Team[]>("/teams")
      .then((list) => setTeams([...list].sort(byName)))
      .catch((err: Error) => {
        setTeams([]);
        notifications.show({ color: "red", title: "Could not load teams", message: err.message });
      });
    api
      .get<TeamService[]>("/teams/services")
      .then(setServices)
      .catch(() => setServices([]));
  }, []);

  function upsert(team: Team) {
    setTeams((list) => [...(list ?? []).filter((t) => t.id !== team.id), team].sort(byName));
  }

  function remove(teamId: number) {
    setTeams((list) => (list ?? []).filter((t) => t.id !== teamId));
  }

  function added(team: Team) {
    upsert(team);
    setAdding(false);
  }

  return (
    <Stack gap="sm">
      <Group justify="space-between" align="flex-end">
        <div>
          <Title order={3}>Teams</Title>
          <Text size="sm" c="dimmed">
            Each student team&apos;s repository, Linear team, Coolify server, and other links.
            Dashed buttons haven&apos;t been set up yet: click one to set it up, or use Find links
            in a team&apos;s menu.
          </Text>
        </div>
        <Button leftSection={<IconPlus size={16} />} onClick={() => setAdding(true)}>
          Add team
        </Button>
      </Group>

      {teams === null ? (
        <SimpleGrid cols={{ base: 1, sm: 2, lg: 3 }}>
          {[0, 1, 2].map((i) => (
            <Skeleton key={i} h={96} />
          ))}
        </SimpleGrid>
      ) : teams.length === 0 ? (
        <Card withBorder padding="xl" style={{ borderStyle: "dashed" }}>
          <Stack align="center" gap="xs">
            <IconUsersGroup size={32} stroke={1.5} />
            <Text fw={500}>No teams yet</Text>
            <Text size="sm" c="dimmed" ta="center">
              Type a team&apos;s name and its GitHub repository, Linear team, and Coolify server are
              found for you (and anything missing can be created).
            </Text>
            <Button
              variant="light"
              leftSection={<IconPlus size={16} />}
              mt="xs"
              onClick={() => setAdding(true)}
            >
              Add team
            </Button>
          </Stack>
        </Card>
      ) : (
        <SimpleGrid cols={{ base: 1, sm: 2, lg: 3 }}>
          {teams.map((t) => (
            <TeamCard
              key={t.id}
              team={t}
              services={services}
              onChange={upsert}
              onDeleted={remove}
            />
          ))}
        </SimpleGrid>
      )}

      <Modal opened={adding} onClose={() => setAdding(false)} title="Add team" size="lg">
        <AddTeamDialog services={services} onAdded={added} />
      </Modal>
    </Stack>
  );
}
