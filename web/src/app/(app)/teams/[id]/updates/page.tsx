"use client";

// /teams/<id>/updates: a team's recent GitHub and Linear activity.

import { useParams } from "next/navigation";

import { TeamUpdates } from "@/components/teams/TeamUpdates";

export default function TeamUpdatesPage() {
  const { id } = useParams<{ id: string }>();
  return <TeamUpdates teamId={Number(id)} />;
}
