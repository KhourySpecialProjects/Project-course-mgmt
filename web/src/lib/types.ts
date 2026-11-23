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
  /** Every personal and shared key the tool uses (never their values). */
  credentials: { key: string; label: string; scope: "user" | "system"; required: boolean }[];
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
  scope: "user" | "system" | "team";
  help_url: string | null;
  placeholder: string;
  is_set: boolean;
  /** Last 4 characters of the saved value (empty for short values). */
  hint: string;
  /** False when a value is saved but can no longer be decrypted. */
  readable: boolean;
  updated_at: string | null;
}

// --- Coolify panel (api/app/modules/coolify/schemas.py) -----------------------

export type CoolifyResourceKind = "applications" | "databases" | "services";
export type CoolifyAction = "start" | "stop" | "restart" | "redeploy";
export type ServerJobKind = "patch_check" | "patch_security" | "patch_all" | "image_scan";

/** Coolify's image-scan verdict, as its Security tab shows it. */
export interface SecurityInfo {
  /** update_now | update_available | no_fix | check_needed | ok | not_checked */
  status: string;
  label: string;
  action: string;
  problem_count: number;
  exploited_count: number;
  critical_count: number;
  high_count: number;
  medium_count: number;
  eol: boolean | null;
  checked_at: string | null;
}

export interface PackageUpdate {
  package: string;
  current_version: string;
  new_version: string;
  security: boolean;
}

export interface ImageScan {
  image: string;
  error?: string;
  counts?: Record<string, number>;
  fixable?: number;
  findings?: {
    id: string;
    severity: string;
    package: string;
    version: string;
    fixed_in: string;
    url: string;
  }[];
}

export interface ServerJob {
  id: number;
  kind: ServerJobKind;
  server_uuid: string;
  server_name: string;
  status: "running" | "succeeded" | "failed";
  log: string;
  /** Patch jobs: update_count, security_count, reboot_required, updates. Scans: images. */
  result: {
    update_count?: number;
    security_count?: number;
    reboot_required?: boolean;
    updates?: PackageUpdate[];
    images?: ImageScan[];
  } | null;
  error: string;
  started_by: string | null;
  created_at: string;
  finished_at: string | null;
}

export interface CoolifyServer {
  uuid: string;
  name: string;
  ip: string;
  reachable: boolean | null;
  usable: boolean | null;
  image_scanning: boolean | null;
  last_patch_check: ServerJob | null;
  last_image_scan: ServerJob | null;
  running_job: ServerJob | null;
}

export interface CoolifyResource {
  kind: CoolifyResourceKind;
  uuid: string;
  name: string;
  /** e.g. "running:healthy", "exited:unhealthy" */
  status: string;
  project: string;
  environment: string;
  fqdn: string | null;
  git_repository: string | null;
  git_branch: string | null;
  security: SecurityInfo | null;
}

export interface CoolifyOverview {
  team_name: string;
  token_set: boolean;
  /** The workbench can make this team's token itself (you have a Coolify admin token). */
  auto_connect: boolean;
  dashboard_url: string | null;
  coolify_team: string | null;
  error: string | null;
  security_error: string | null;
  servers: CoolifyServer[];
  resources: CoolifyResource[];
}

export interface CoolifyActionResult {
  message: string;
  deployment_uuid: string | null;
}

export interface CoolifyDeployment {
  uuid: string;
  status: string;
  commit: string | null;
  commit_message: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface CoolifyDeploymentDetail extends CoolifyDeployment {
  log: { output: string; type: string }[];
}

export interface CoolifyEnv {
  uuid: string;
  key: string;
  /** null when Coolify won't show it (locked, or the token can't read secrets). */
  value: string | null;
  is_buildtime: boolean;
  is_preview: boolean;
  is_literal: boolean;
  is_multiline: boolean;
  is_shown_once: boolean;
}

export interface CoolifyFinding {
  id: string;
  title: string;
  severity: string;
  package: string;
  version: string;
  fixed_in: string;
  state: string;
  kev: boolean;
  url: string;
  image: string;
}

export interface CoolifyFindings {
  security: SecurityInfo | null;
  images: string[];
  findings: CoolifyFinding[];
  total: number;
}

export interface TeamSecurity {
  team_id: number;
  team_name: string;
  token_set: boolean;
  auto_connect: boolean;
  error: string | null;
  resources: CoolifyResource[];
  servers: CoolifyServer[];
}

export interface CoolifyAutoConnect {
  coolify_team: string;
  message: string;
}
