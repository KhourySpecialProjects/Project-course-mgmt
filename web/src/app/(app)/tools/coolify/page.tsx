// Served at /tools/coolify. The page itself stays tiny; the module's code lives
// in src/modules/coolify so each tool is self-contained.
import { CoolifyToolPage } from "@/modules/coolify/CoolifyToolPage";

export default function Page() {
  return <CoolifyToolPage />;
}
