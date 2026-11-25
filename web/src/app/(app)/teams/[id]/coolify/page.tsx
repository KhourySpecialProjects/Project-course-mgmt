"use client";

// /teams/<id>/coolify: one team's Coolify panel.

import { useParams } from "next/navigation";

import { CoolifyTeamPanel } from "@/modules/coolify/CoolifyTeamPanel";

export default function TeamCoolifyPage() {
  const { id } = useParams<{ id: string }>();
  return <CoolifyTeamPanel teamId={Number(id)} />;
}
