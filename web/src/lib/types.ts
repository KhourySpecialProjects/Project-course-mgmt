// TypeScript shapes for data the API returns. Keep these in sync with the
// Pydantic schemas in api/app/**/schemas.py. (The full, always-current list is
// at http://localhost:8000/api/docs.)

export interface User {
  id: number;
  email: string;
  full_name: string;
  is_active: boolean;
  is_superuser: boolean;
  created_at: string;
}

export interface ToolInfo {
  id: string;
  name: string;
  description: string;
  configured: boolean;
}

export interface ToolStatus {
  configured: boolean;
  message: string;
  missing_user_credentials: string[];
  missing_system_credentials: string[];
}

export type InviteStatus = "pending" | "accepted" | "revoked" | "expired";

export interface Invite {
  id: number;
  email: string;
  full_name: string;
  is_superuser: boolean;
  status: InviteStatus;
  created_at: string;
  expires_at: string;
  accepted_at: string | null;
  created_by_email: string | null;
}

/** Returned only when an invite is created. The token is never shown again. */
export interface InviteCreated extends Invite {
  token: string;
}

export interface InvitePreview {
  email: string;
  full_name: string;
  expires_at: string;
}

export interface TeamLink {
  id: number;
  /** The built-in service this link belongs to ("github", ...), or null for a custom link. */
  service_id: string | null;
  label: string;
  url: string;
  created_at: string;
}

export interface Team {
  id: number;
  name: string;
  links: TeamLink[];
  created_at: string;
}

/** A service that can create something for each team: a GitHub repo, a Linear team, ... */
export interface TeamService {
  id: string;
  name: string;
  /** What it links to: "repository", "team", "server". */
  resource_name: string;
  summary: string;
  /** False for services that only find things (a team's server), never make them. */
  can_create: boolean;
  /** Whether the current user has the keys it needs; if not, `message` says what's missing. */
  configured: boolean;
  message: string;
  missing_user_credentials: string[];
  missing_system_credentials: string[];
}

export interface TeamServiceCreated {
  team: Team;
  message: string;
}

export type ConnectOutcome =
  "linked" | "already_linked" | "not_found" | "taken" | "not_set_up" | "error";

/** What "Find links" (POST /api/teams/{id}/connect) did for each service. */
export interface TeamConnected {
  team: Team;
  results: { service_id: string; outcome: ConnectOutcome; message: string }[];
}

/** What one service already has for a team name (GET /api/teams/lookup). */
export interface ServiceLookup {
  service_id: string;
  configured: boolean;
  found: { url: string; label: string; external_id: string } | null;
  /** Name of the workbench team `found` is already linked to, if it's taken. */
  linked_team: string | null;
  /** Why the search couldn't be done: missing keys, or the service's error. */
  error: string | null;
}

export interface TeamLookup {
  name: string;
  /** A workbench team already has this name. */
  name_taken: boolean;
  services: ServiceLookup[];
}

export interface CredentialStatus {
  key: string;
  label: string;
  description: string;
  scope: "user" | "system";
  help_url: string | null;
  placeholder: string;
  is_set: boolean;
  /** Last 4 characters of the saved value (empty for short values). */
  hint: string;
  /** False when a value is saved but can no longer be decrypted. */
  readable: boolean;
  updated_at: string | null;
}
