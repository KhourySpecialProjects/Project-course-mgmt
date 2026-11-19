// Served at /tools/github. The page itself stays tiny; the module's code lives
// in src/modules/github so each tool is self-contained.
import { GitHubToolPage } from "@/modules/github/GitHubToolPage";

export default function Page() {
  return <GitHubToolPage />;
}
