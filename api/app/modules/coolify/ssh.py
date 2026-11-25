"""Running commands on a team's server over SSH, the way Coolify itself does.

Coolify's API can't patch a server's operating system or start an image scan on
demand, so the workbench connects with the same SSH key Coolify uses for that
server (read through the team's Coolify token, never stored) and runs:

- a patch check:   which system packages have updates, and which are security fixes
- patching:        install the security updates (or all of them)
- an image scan:   Grype (the scanner Coolify uses) on every running container's image

Only apt-based servers (Debian, Ubuntu) can be patched for now; that's what the
course droplets run. Tests replace ``connect`` with a fake.
"""

import base64
import io
import json
import re
import shlex
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol

import paramiko

from app.core.http import ExternalServiceError

SEVERITIES = ("critical", "high", "medium", "low", "negligible", "unknown")
GRYPE_IMAGE = "anchore/grype:latest"
APT_ENV = "DEBIAN_FRONTEND=noninteractive"
DPKG_OPTS = "-o Dpkg::Options::=--force-confdef -o Dpkg::Options::=--force-confold"


class Shell(Protocol):
    """Something that runs a command on the server: (command, timeout) -> (exit code, output)."""

    def run(self, command: str, timeout: float = 300) -> tuple[int, str]: ...

    def close(self) -> None: ...


@dataclass(frozen=True)
class SshTarget:
    host: str
    port: int
    user: str
    private_keys: Sequence[str]


class _ParamikoShell:
    def __init__(self, client: paramiko.SSHClient, sudo: bool) -> None:
        self._client = client
        self._sudo = sudo

    def run(self, command: str, timeout: float = 300) -> tuple[int, str]:
        if self._sudo:
            command = f"sudo -n sh -c {shlex.quote(command)}"
        _, stdout, stderr = self._client.exec_command(command, timeout=timeout)
        out = stdout.read().decode(errors="replace")
        err = stderr.read().decode(errors="replace")
        return stdout.channel.recv_exit_status(), out + err

    def close(self) -> None:
        self._client.close()


def _load_key(text: str) -> paramiko.PKey | None:
    for cls in (paramiko.Ed25519Key, paramiko.RSAKey, paramiko.ECDSAKey):
        try:
            return cls.from_private_key(io.StringIO(text))
        except (paramiko.SSHException, ValueError):
            continue
    return None


def connect(target: SshTarget) -> Shell:
    """Log in with the first of the keys the server accepts."""
    if not target.private_keys:
        raise ExternalServiceError(
            "Coolify didn't share any SSH keys. Give this team's Coolify token the "
            "read:sensitive permission (its owner must be an admin of the Coolify team)."
        )
    last_error = "no usable key"
    for text in target.private_keys:
        key = _load_key(text)
        if key is None:
            continue
        client = paramiko.SSHClient()
        # Coolify connects without checking host keys too; the address comes from Coolify.
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            client.connect(
                target.host,
                port=target.port,
                username=target.user,
                pkey=key,
                timeout=15,
                allow_agent=False,
                look_for_keys=False,
            )
        except paramiko.AuthenticationException:
            client.close()
            last_error = "key not accepted"
            continue
        except (OSError, paramiko.SSHException) as err:
            client.close()
            raise ExternalServiceError(f"Couldn't connect to {target.host}: {err}") from None
        return _ParamikoShell(client, sudo=target.user != "root")
    raise ExternalServiceError(
        f"Couldn't log in to {target.user}@{target.host} with Coolify's SSH keys ({last_error})."
    )


# --- patching ---------------------------------------------------------------


@dataclass(frozen=True)
class PackageUpdate:
    package: str
    current_version: str
    new_version: str
    security: bool


@dataclass
class PatchStatus:
    updates: list[PackageUpdate] = field(default_factory=list)
    reboot_required: bool = False

    @property
    def security_updates(self) -> list[PackageUpdate]:
        return [u for u in self.updates if u.security]

    def summary(self) -> dict[str, Any]:
        return {
            "update_count": len(self.updates),
            "security_count": len(self.security_updates),
            "reboot_required": self.reboot_required,
            "updates": [u.__dict__ for u in self.updates],
        }


# openssl/jammy-updates,jammy-security 3.0.2-0ubuntu1.18 amd64 [upgradable from: 3.0.2-0ubuntu1.15]
_APT_LINE = re.compile(
    r"^(?P<pkg>[^/\s]+)/(?P<suites>\S+)\s+(?P<new>\S+)\s+\S+\s+\[upgradable from: (?P<old>[^\]]+)\]"
)


def parse_apt_upgradable(output: str) -> list[PackageUpdate]:
    updates = []
    for line in output.splitlines():
        m = _APT_LINE.match(line.strip())
        if m:
            updates.append(
                PackageUpdate(
                    package=m["pkg"],
                    current_version=m["old"],
                    new_version=m["new"],
                    security="-security" in m["suites"],
                )
            )
    return updates


def _require_apt(shell: Shell, log: Callable[[str], None]) -> None:
    code, _ = shell.run("command -v apt-get", timeout=30)
    if code != 0:
        raise ExternalServiceError(
            "This server doesn't use apt (Debian/Ubuntu); only apt servers can be patched here."
        )


def check_patches(shell: Shell, log: Callable[[str], None]) -> PatchStatus:
    _require_apt(shell, log)
    log("Refreshing the package lists (apt-get update)...")
    code, out = shell.run(f"{APT_ENV} apt-get update -qq", timeout=600)
    if code != 0:
        raise ExternalServiceError(f"apt-get update failed:\n{out[-2000:]}")
    _, out = shell.run("apt list --upgradable 2>/dev/null", timeout=120)
    _, reboot = shell.run("test -f /var/run/reboot-required && echo yes || echo no", timeout=30)
    status = PatchStatus(updates=parse_apt_upgradable(out), reboot_required="yes" in reboot)
    log(
        f"{len(status.updates)} update(s) available, {len(status.security_updates)} of them "
        "security fixes." + (" A reboot is needed." if status.reboot_required else "")
    )
    return status


def apply_patches(shell: Shell, log: Callable[[str], None], *, security_only: bool) -> PatchStatus:
    before = check_patches(shell, log)
    if security_only:
        packages = [u.package for u in before.security_updates]
        if not packages:
            log("No security updates to install.")
            return before
        log(f"Installing {len(packages)} security update(s): {', '.join(packages)}")
        names = " ".join(shlex.quote(p) for p in packages)
        command = f"{APT_ENV} apt-get install -y --only-upgrade {DPKG_OPTS} {names}"
    else:
        if not before.updates:
            log("Nothing to update.")
            return before
        log(f"Installing all {len(before.updates)} update(s)...")
        command = f"{APT_ENV} apt-get upgrade -y {DPKG_OPTS}"
    code, out = shell.run(command, timeout=1800)
    log(out[-6000:])
    if code != 0:
        raise ExternalServiceError(f"The update failed (exit code {code}). See the log above.")
    log("Checking again...")
    return check_patches(shell, log)


# --- image scans ------------------------------------------------------------


def _finding(match: dict[str, Any]) -> dict[str, Any]:
    vuln = match.get("vulnerability") or {}
    artifact = match.get("artifact") or {}
    fix = vuln.get("fix") or {}
    return {
        "id": vuln.get("id", ""),
        "severity": str(vuln.get("severity", "unknown")).lower(),
        "package": artifact.get("name", ""),
        "version": artifact.get("version", ""),
        "fixed_in": ", ".join(fix.get("versions") or []),
        "url": vuln.get("dataSource", ""),
    }


def summarize_grype(image: str, report: dict[str, Any], *, keep: int = 50) -> dict[str, Any]:
    """Counts by severity, and the worst findings first."""
    findings = [_finding(m) for m in report.get("matches") or [] if isinstance(m, dict)]
    counts = {s: 0 for s in SEVERITIES}
    for f in findings:
        counts[f["severity"] if f["severity"] in counts else "unknown"] += 1
    rank = {s: i for i, s in enumerate(SEVERITIES)}
    findings.sort(key=lambda f: (rank.get(f["severity"], 99), not f["fixed_in"], f["package"]))
    return {
        "image": image,
        "counts": counts,
        "fixable": sum(1 for f in findings if f["fixed_in"]),
        "findings": findings[:keep],
    }


def scan_images(shell: Shell, log: Callable[[str], None]) -> dict[str, Any]:
    code, out = shell.run("docker ps --format '{{.Image}}'", timeout=60)
    if code != 0:
        raise ExternalServiceError(f"Couldn't list the server's containers:\n{out[-1000:]}")
    images = sorted({line.strip() for line in out.splitlines() if line.strip()})
    images = [i for i in images if not i.startswith("anchore/grype")]
    log(f"{len(images)} running image(s): {', '.join(images) or 'none'}")
    results = []
    for image in images:
        log(f"Scanning {image}...")
        command = (
            "docker run --rm -v /var/run/docker.sock:/var/run/docker.sock "
            f"-v workbench-grype-db:/root/.cache/grype {GRYPE_IMAGE} "
            f"{shlex.quote(image)} -o json -q"
        )
        code, out = shell.run(command, timeout=1800)
        start = out.find("{")
        try:
            report = json.loads(out[start:]) if code == 0 and start >= 0 else None
        except ValueError:
            report = None
        if not isinstance(report, dict):
            log(f"  couldn't scan {image}: {out[-500:].strip()}")
            results.append({"image": image, "error": out[-500:].strip() or f"exit {code}"})
            continue
        summary = summarize_grype(image, report)
        c = summary["counts"]
        log(f"  {c['critical']} critical, {c['high']} high, {c['medium']} medium")
        results.append(summary)
    return {"images": results}


# --- running Coolify's own code on the Coolify server ---------------------------
#
# Coolify's API can't create API tokens; only its token page can, by calling
# createToken() inside the app. On the Coolify server, the workbench runs that same
# code in Coolify's container (php artisan tinker), so each team's token can be
# made automatically.

_MARKER = "WBJSON:"


def coolify_container(shell: Shell) -> str:
    """Name of the main Coolify app container on the Coolify server."""
    for flt in ("name=^coolify$", "label=com.docker.compose.service=coolify"):
        code, out = shell.run(
            f"docker ps --filter {shlex.quote(flt)} --format '{{{{.Names}}}}'", 30
        )
        names = [n.strip() for n in out.splitlines() if n.strip()] if code == 0 else []
        if names:
            return names[0]
    raise ExternalServiceError(
        "Couldn't find Coolify's container on the Coolify server. Is this the server that "
        "runs the Coolify dashboard?"
    )


def run_coolify_php(shell: Shell, container: str, php: str, data: Any = None) -> Any:
    """Run PHP inside Coolify (``$in`` holds ``data``); it must print one WBJSON: line."""
    payload = base64.b64encode(json.dumps(data).encode()).decode()
    code_b64 = base64.b64encode(
        f"$in = json_decode(base64_decode('{payload}'), true);\n{php}".encode()
    ).decode()
    command = (
        f"docker exec {shlex.quote(container)} php artisan tinker "
        f"--execute=\"eval(base64_decode('{code_b64}'));\""
    )
    code, out = shell.run(command, timeout=180)
    for line in out.splitlines():
        line = line.strip()
        if line.startswith(_MARKER):
            return json.loads(line[len(_MARKER) :])
    raise ExternalServiceError(f"Coolify's command didn't work (exit {code}):\n{out[-800:]}")


COOLIFY_TEAMS_PHP = r"""
$out = [];
foreach (\App\Models\Team::with(['servers', 'members'])->get() as $t) {
    $admins = [];
    foreach ($t->members as $m) {
        if (in_array($m->pivot->role ?? '', ['owner', 'admin'])) {
            $admins[] = ['id' => $m->id, 'email' => $m->email, 'role' => $m->pivot->role];
        }
    }
    $out[] = ['id' => $t->id, 'name' => $t->name,
              'ips' => $t->servers->pluck('ip')->values()->all(), 'admins' => $admins];
}
echo "WBJSON:" . json_encode($out) . "\n";
"""

CREATE_TOKEN_PHP = r"""
$user = \App\Models\User::findOrFail($in['user_id']);
$user->tokens()->where('team_id', $in['team_id'])->where('name', $in['name'])->delete();
$token = $user->createToken($in['name'], $in['abilities'], null, $in['team_id']);
echo "WBJSON:" . json_encode(['token' => $token->plainTextToken]) . "\n";
"""


def coolify_teams(shell: Shell, container: str) -> list[dict[str, Any]]:
    teams = run_coolify_php(shell, container, COOLIFY_TEAMS_PHP)
    return [t for t in teams if isinstance(t, dict)] if isinstance(teams, list) else []


def create_team_token(
    shell: Shell, container: str, *, team_id: int, user_id: int, name: str, abilities: list[str]
) -> str:
    """A new token for ``team_id`` owned by ``user_id`` (older ones with this name are revoked)."""
    data = {"team_id": team_id, "user_id": user_id, "name": name, "abilities": abilities}
    result = run_coolify_php(shell, container, CREATE_TOKEN_PHP, data)
    token = result.get("token") if isinstance(result, dict) else None
    if not isinstance(token, str) or "|" not in token:
        raise ExternalServiceError("Coolify didn't return a token.")
    return token
