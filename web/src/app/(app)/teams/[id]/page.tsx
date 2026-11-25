"use client";

// /teams/<id>: one team's page (students, links, status, updates, Coolify).

import { useParams } from "next/navigation";

import { TeamPage } from "@/components/teams/TeamPage";

export default function Page() {
  const { id } = useParams<{ id: string }>();
  return <TeamPage teamId={Number(id)} />;
}
