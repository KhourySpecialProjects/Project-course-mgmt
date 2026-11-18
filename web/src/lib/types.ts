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
}
