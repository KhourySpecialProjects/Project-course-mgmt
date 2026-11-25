import type { User } from "@/lib/types";

/**
 * Where a user manages their API keys. Superusers have every key (their own
 * and the shared ones) in System settings; everyone else uses their Account page.
 */
export function apiKeysPath(user: User | null | undefined): string {
  return user?.is_superuser ? "/admin/settings" : "/account?tab=api-keys";
}
