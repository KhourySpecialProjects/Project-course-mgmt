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
