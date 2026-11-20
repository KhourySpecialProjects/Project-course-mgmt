// Registry of tool modules shown in the sidebar and on the dashboard.
//
// To add a tool:
//   1. Create src/modules/<id>/ with its components.
//   2. Add a page at src/app/(app)/tools/<id>/page.tsx.
//   3. Add an entry below. The `id` must match the API module's id
//      (api/app/modules/<id>/module.py).
// See docs/adding-a-tool-module.md for the full walkthrough.

import {
  IconBrandGithub,
  IconLayoutKanban,
  IconLink,
  IconRocket,
  type Icon,
} from "@tabler/icons-react";
import { type ComponentProps, createElement } from "react";

export interface ToolModuleEntry {
  id: string;
  name: string;
  href: string;
  icon: Icon;
}

export const toolModules: ToolModuleEntry[] = [
  { id: "github", name: "GitHub", href: "/tools/github", icon: IconBrandGithub },
  { id: "linear", name: "Linear", href: "/tools/linear", icon: IconLayoutKanban },
  { id: "coolify", name: "Coolify", href: "/tools/coolify", icon: IconRocket },
];

/**
 * A tool module's icon, by module id (a plain link icon for anything else).
 * Used on team cards: <ToolIcon toolId="github" size={14} />
 */
export function ToolIcon({ toolId, ...props }: { toolId: string | null } & ComponentProps<Icon>) {
  return createElement(toolModules.find((m) => m.id === toolId)?.icon ?? IconLink, props);
}
