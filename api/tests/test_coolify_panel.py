"""The team Coolify panel, the course-wide Security page, and server jobs.

Coolify is faked with ``fake_http`` (from test_teams) and SSH with ``FakeShell``.
"""

import base64
import json
import re
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.core import http
from app.core.http import ExternalServiceError
from app.modules.coolify import ssh
from tests.conftest import FakeHttp
from tests.test_teams import _create_team

C = "https://coolify.test/api/v1"
TOKEN = "1|team-token-abcdefgh"
KEY = "-----BEGIN OPENSSH PRIVATE KEY-----\nfake\n-----END OPENSSH PRIVATE KEY-----\n"


def _setup(client: TestClient, team_name: str = "Before Dawn") -> dict[str, Any]:
    assert client.put(
        "/api/credentials/system/coolify_url", json={"value": "coolify.test"}
    ).is_success
    team = _create_team(client, team_name)
    r = client.put(f"/api/teams/{team['id']}/credentials/coolify_team_token", json={"value": TOKEN})
    assert r.status_code == 200, r.text
    return team


def _fake_coolify(fake: FakeHttp, *, vulnerabilities: Any = None) -> None:
    fake.on("GET", f"{C}/team", {"id": 3, "name": "Before Dawn Practicum Team"})
    fake.on(
        "GET",
        f"{C}/servers",
        [
            {
                "uuid": "srv1",
                "name": "before dawn server",
                "ip": "203.0.113.2",
                "user": "root",
                "port": 22,
                "settings": {"is_reachable": True, "is_usable": True},
            }
        ],
    )
    fake.on(
        "GET",
        f"{C}/servers/srv1",
        {
            "uuid": "srv1",
            "name": "before dawn server",
            "ip": "203.0.113.2",
            "user": "root",
            "port": 22,
        },
    )
    fake.on("GET", f"{C}/servers/srv1/image-scanning", {"is_image_scan_enabled": True})
    fake.on(
        "GET",
        f"{C}/applications",
        [
            {
                "uuid": "app1",
                "name": "ssa dev",
                "status": "running:healthy",
                "environment_id": 7,
                "fqdn": "https://dev.ssa.test",
            },
            {"uuid": "app2", "name": "ssa prod", "status": "exited:unhealthy", "environment_id": 7},
        ],
    )
    fake.on(
        "GET",
        f"{C}/databases",
        [{"uuid": "db1", "name": "postgres", "status": "running:healthy", "environment_id": 7}],
    )
    fake.on("GET", f"{C}/services", [])
    fake.on("GET", f"{C}/projects", [{"uuid": "p1", "name": "ssa-portal"}])
    fake.on("GET", f"{C}/projects/p1/environments", [{"id": 7, "name": "production"}])
    fake.on(
        "GET",
        f"{C}/vulnerabilities",
        vulnerabilities
        if vulnerabilities is not None
        else {
            "resources": [
                {
                    "uuid": "app1",
                    "name": "ssa dev",
                    "type": "application",
                    "security": {
                        "status": "update_now",
                        "label": "Update now",
                        "action": "Redeploy to pick up the fixed base image",
                        "problem_count": 12,
                        "exploited_count": 1,
                        "critical_count": 2,
                        "high_count": 5,
                        "medium_count": 5,
                    },
                }
            ]
        },
    )


def test_team_token_is_saved_but_never_shown(staff: TestClient) -> None:
    team = _setup(staff)
    creds = staff.get(f"/api/teams/{team['id']}/credentials").json()
    [token] = [c for c in creds if c["key"] == "coolify_team_token"]
    assert token["is_set"] is True
    assert token["hint"] == "efgh"
    assert TOKEN not in json.dumps(creds)
    # Team tokens aren't personal or shared keys.
    assert "coolify_team_token" not in {c["key"] for c in staff.get("/api/credentials/me").json()}
    assert (
        staff.put(f"/api/teams/{team['id']}/credentials/nope", json={"value": "x"}).status_code
        == 404
    )
    assert (
        staff.delete(f"/api/teams/{team['id']}/credentials/coolify_team_token").status_code == 204
    )


def test_overview_shows_servers_resources_and_security(
    staff: TestClient, fake_http: FakeHttp
) -> None:
    team = _setup(staff)
    _fake_coolify(fake_http)

    r = staff.get(f"/api/tools/coolify/teams/{team['id']}/overview")
    assert r.status_code == 200, r.text
    o = r.json()
    assert o["coolify_team"] == "Before Dawn Practicum Team"
    assert o["error"] is None
    [server] = o["servers"]
    assert (server["name"], server["ip"], server["reachable"], server["image_scanning"]) == (
        "before dawn server",
        "203.0.113.2",
        True,
        True,
    )
    by_name = {x["name"]: x for x in o["resources"]}
    assert set(by_name) == {"ssa dev", "ssa prod", "postgres"}
    dev = by_name["ssa dev"]
    assert (dev["kind"], dev["project"], dev["environment"]) == (
        "applications",
        "ssa-portal",
        "production",
    )
    assert dev["security"]["status"] == "update_now"
    assert dev["security"]["critical_count"] == 2
    assert by_name["ssa prod"]["security"] is None
    # Every call used the team's own token.
    assert {h["Authorization"] for *_, h in fake_http.calls} == {f"Bearer {TOKEN}"}


def test_overview_explains_what_is_missing(staff: TestClient, fake_http: FakeHttp) -> None:
    team = _create_team(staff, "Team A")
    o = staff.get(f"/api/tools/coolify/teams/{team['id']}/overview").json()
    assert "Coolify dashboard address" in o["error"]

    staff.put("/api/credentials/system/coolify_url", json={"value": "coolify.test"})
    o = staff.get(f"/api/tools/coolify/teams/{team['id']}/overview").json()
    assert o["token_set"] is False
    assert o["error"] is None

    staff.put(f"/api/teams/{team['id']}/credentials/coolify_team_token", json={"value": TOKEN})
    fake_http.on(
        "GET", f"{C}/team", http.HttpError(403, {"success": False, "message": "API is disabled."})
    )
    o = staff.get(f"/api/tools/coolify/teams/{team['id']}/overview").json()
    assert o["error"].startswith("Coolify's API is turned off.")
    assert "Settings → Advanced → API and MCP" in o["error"]


def test_resource_actions(staff: TestClient, fake_http: FakeHttp) -> None:
    team = _setup(staff)
    base = f"/api/tools/coolify/teams/{team['id']}/resources"
    fake_http.on(
        "POST",
        f"{C}/applications/app1/start?force=true",
        {"message": "Deployment request queued.", "deployment_uuid": "dep9"},
    )
    fake_http.on(
        "POST", f"{C}/applications/app1/stop", {"message": "Application stopping request queued."}
    )
    fake_http.on(
        "POST",
        f"{C}/services/svc1/restart?latest=true",
        {"message": "Service restarting request queued."},
    )
    fake_http.on(
        "POST", f"{C}/databases/db1/restart", {"message": "Database restarting request queued."}
    )

    r = staff.post(f"{base}/applications/app1/redeploy")
    assert r.json() == {"message": "Deployment request queued.", "deployment_uuid": "dep9"}
    assert (
        staff.post(f"{base}/applications/app1/stop")
        .json()["message"]
        .startswith("Application stopping")
    )
    assert staff.post(f"{base}/services/svc1/redeploy").status_code == 200  # pulls latest images
    assert staff.post(f"{base}/databases/db1/redeploy").status_code == 200  # restarts
    assert staff.post(f"{base}/servers/x/start").status_code == 422
    assert staff.post(f"{base}/applications/app1/delete").status_code == 422


def test_actions_need_the_right_token_permissions(staff: TestClient, fake_http: FakeHttp) -> None:
    team = _setup(staff)
    fake_http.on(
        "POST",
        f"{C}/applications/app1/stop",
        http.HttpError(403, {"message": "Missing required permissions: deploy"}),
    )
    r = staff.post(f"/api/tools/coolify/teams/{team['id']}/resources/applications/app1/stop")
    assert r.status_code == 502
    assert "Missing required permissions: deploy" in r.json()["detail"]
    assert TOKEN not in r.text


def test_logs_and_deployments(staff: TestClient, fake_http: FakeHttp) -> None:
    team = _setup(staff)
    t = f"/api/tools/coolify/teams/{team['id']}"
    fake_http.on("GET", f"{C}/applications/app1/logs?lines=300", {"logs": "listening on :3000\n"})
    fake_http.on(
        "GET",
        f"{C}/deployments/applications/app1?take=10",
        {
            "count": 1,
            "deployments": [{"deployment_uuid": "dep1", "status": "failed", "commit": "a1b2c3"}],
        },
    )
    log = [
        {"output": "Building...", "type": "stdout", "hidden": False},
        {"output": "secret internal step", "type": "stdout", "hidden": True},
        {"output": "Module not found: ./Navbar", "type": "stderr", "hidden": False},
    ]
    fake_http.on(
        "GET",
        f"{C}/deployments/dep1",
        {"deployment_uuid": "dep1", "status": "failed", "logs": json.dumps(log)},
    )
    fake_http.on("POST", f"{C}/deployments/dep1/cancel", {"message": "Deployment cancelled."})

    assert staff.get(f"{t}/applications/app1/logs").json() == {"logs": "listening on :3000\n"}
    [dep] = staff.get(f"{t}/applications/app1/deployments").json()
    assert (dep["uuid"], dep["status"], dep["commit"]) == ("dep1", "failed", "a1b2c3")
    detail = staff.get(f"{t}/deployments/dep1").json()
    assert detail["log"] == [
        {"output": "Building...", "type": "stdout"},
        {"output": "Module not found: ./Navbar", "type": "stderr"},
    ]
    assert staff.post(f"{t}/deployments/dep1/cancel").json()["message"] == "Deployment cancelled."


def test_environment_variables(staff: TestClient, fake_http: FakeHttp) -> None:
    team = _setup(staff)
    url = f"/api/tools/coolify/teams/{team['id']}/applications/app1/envs"
    envs = [
        {"uuid": "e1", "key": "PORT", "value": "3000", "is_buildtime": True},
        {"uuid": "e2", "key": "API_SECRET", "value": "hidden-forever", "is_shown_once": True},
    ]
    fake_http.on("GET", f"{C}/applications/app1/envs", envs)
    fake_http.on("POST", f"{C}/applications/app1/envs", {"uuid": "e3"})
    fake_http.on("PATCH", f"{C}/applications/app1/envs", {"uuid": "e1"})
    fake_http.on(
        "DELETE", f"{C}/applications/app1/envs/e1", {"message": "Environment variable deleted."}
    )

    listed = staff.get(url).json()
    assert listed[0]["value"] == "3000"
    assert listed[1]["value"] is None  # locked in Coolify: never shown
    assert staff.post(url, json={"key": "NODE_ENV", "value": "production"}).status_code == 201
    assert fake_http.calls[-2][2] == {
        "key": "NODE_ENV",
        "value": "production",
        "is_preview": False,
        "is_literal": False,
        "is_multiline": False,
    }
    assert staff.patch(url, json={"key": "PORT", "value": "8080"}).status_code == 200
    assert staff.delete(f"{url}/e1").status_code == 200
    assert staff.post(url, json={"key": "HAS SPACE", "value": "x"}).status_code == 422


def test_vulnerability_findings(staff: TestClient, fake_http: FakeHttp) -> None:
    team = _setup(staff)
    fake_http.on(
        "GET",
        f"{C}/applications/app1/vulnerabilities?page=1&per_page=100",
        {
            "security": {"status": "update_now", "critical_count": 1},
            "images": [{"image_ref": "ssa-dev:latest", "scan_status": "completed"}],
            "findings": [
                {
                    "display_id": "CVE-2025-1234",
                    "title": "openssl: buffer overflow",
                    "severity": "critical",
                    "package": "openssl",
                    "version": "3.0.2",
                    "fixed_in": "3.0.15",
                    "state": "fixed",
                    "kev": True,
                    "advisory_url": "https://nvd.test/CVE-2025-1234",
                    "image_ref": "ssa-dev:latest",
                }
            ],
            "pagination": {"page": 1, "per_page": 100, "total": 1},
        },
    )
    r = staff.get(
        f"/api/tools/coolify/teams/{team['id']}/resources/applications/app1/vulnerabilities"
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["images"] == ["ssa-dev:latest"]
    [f] = body["findings"]
    assert (f["id"], f["severity"], f["fixed_in"], f["kev"]) == (
        "CVE-2025-1234",
        "critical",
        "3.0.15",
        True,
    )


def test_server_settings_actions(staff: TestClient, fake_http: FakeHttp) -> None:
    team = _setup(staff)
    t = f"/api/tools/coolify/teams/{team['id']}/servers/srv1"
    fake_http.on("PATCH", f"{C}/servers/srv1/image-scanning", {"is_image_scan_enabled": True})
    fake_http.on(
        "POST", f"{C}/servers/srv1/docker-cleanup/run", {"message": "Docker cleanup job queued."}
    )
    assert staff.put(f"{t}/image-scanning", json={"enabled": True}).status_code == 204
    assert fake_http.calls[-1][2] == {"is_image_scan_enabled": True}
    assert staff.post(f"{t}/docker-cleanup").json()["message"] == "Docker cleanup job queued."


def test_course_security_page(staff: TestClient, fake_http: FakeHttp) -> None:
    _setup(staff, "Before Dawn")
    _create_team(staff, "Nimbus")  # no token yet
    _fake_coolify(fake_http)

    rows = {r["team_name"]: r for r in staff.get("/api/tools/coolify/security").json()}
    assert rows["Nimbus"]["token_set"] is False
    bd = rows["Before Dawn"]
    assert bd["error"] is None
    [res] = bd["resources"]
    assert (res["name"], res["kind"], res["security"]["status"]) == (
        "ssa dev",
        "applications",
        "update_now",
    )
    assert [s["name"] for s in bd["servers"]] == ["before dawn server"]


# --- server jobs over SSH -----------------------------------------------------


class FakeShell:
    """Answers commands by the first matching substring; records what was run."""

    def __init__(self, answers: dict[str, tuple[int, str]]) -> None:
        self.answers = answers
        self.commands: list[str] = []
        self.closed = False

    def run(self, command: str, timeout: float = 300) -> tuple[int, str]:
        self.commands.append(command)
        for needle, answer in self.answers.items():
            if needle in command:
                return answer
        return 0, ""

    def close(self) -> None:
        self.closed = True


APT_LIST = """Listing...
openssl/jammy-updates,jammy-security 3.0.2-0ubuntu1.18 amd64 [upgradable from: 3.0.2-0ubuntu1.15]
curl/jammy-updates 7.81.0-1ubuntu1.20 amd64 [upgradable from: 7.81.0-1ubuntu1.16]
libssl3/jammy-security 3.0.2-0ubuntu1.18 amd64 [upgradable from: 3.0.2-0ubuntu1.15]
"""


@pytest.fixture
def shell(monkeypatch: pytest.MonkeyPatch) -> FakeShell:
    fake = FakeShell(
        {
            "command -v apt-get": (0, "/usr/bin/apt-get"),
            "apt list --upgradable": (0, APT_LIST),
            "reboot-required": (0, "yes\n"),
        }
    )
    targets: list[ssh.SshTarget] = []

    def connect(target: ssh.SshTarget) -> FakeShell:
        targets.append(target)
        return fake

    monkeypatch.setattr(ssh, "connect", connect)
    fake.targets = targets  # type: ignore[attr-defined]
    return fake


def _start(client: TestClient, team: dict[str, Any], kind: str) -> dict[str, Any]:
    r = client.post(f"/api/tools/coolify/teams/{team['id']}/servers/srv1/jobs", json={"kind": kind})
    assert r.status_code == 202, r.text
    # TestClient runs background tasks before returning, so the job is finished.
    job: dict[str, Any] = client.get(
        f"/api/tools/coolify/teams/{team['id']}/jobs/{r.json()['id']}"
    ).json()
    return job


def test_patch_check_over_ssh(staff: TestClient, fake_http: FakeHttp, shell: FakeShell) -> None:
    team = _setup(staff)
    _fake_coolify(fake_http)
    fake_http.on("GET", f"{C}/security/keys", [{"uuid": "k1", "name": "coolify"}])
    fake_http.on("GET", f"{C}/security/keys/k1", {"uuid": "k1", "private_key": KEY})

    job = _start(staff, team, "patch_check")
    assert job["status"] == "succeeded", job
    assert job["result"]["update_count"] == 3
    assert job["result"]["security_count"] == 2
    assert job["result"]["reboot_required"] is True
    assert "2 of them security fixes" in job["log"]
    [target] = shell.targets  # type: ignore[attr-defined]
    assert (target.host, target.user, target.port, list(target.private_keys)) == (
        "203.0.113.2",
        "root",
        22,
        [KEY],
    )
    assert shell.closed
    # Nothing was installed.
    assert not any("install" in c or "upgrade -y" in c for c in shell.commands)

    # The panel shows the latest check on the server.
    server = staff.get(f"/api/tools/coolify/teams/{team['id']}/overview").json()["servers"][0]
    assert server["last_patch_check"]["result"]["security_count"] == 2


def test_security_patching_installs_only_security_updates(
    staff: TestClient, fake_http: FakeHttp, shell: FakeShell
) -> None:
    team = _setup(staff)
    _fake_coolify(fake_http)
    fake_http.on("GET", f"{C}/security/keys", [{"uuid": "k1", "private_key": KEY}])

    job = _start(staff, team, "patch_security")
    assert job["status"] == "succeeded", job
    [install] = [c for c in shell.commands if "apt-get install" in c]
    assert "--only-upgrade" in install
    assert "openssl" in install and "libssl3" in install and "curl" not in install


def test_jobs_explain_missing_ssh_access(staff: TestClient, fake_http: FakeHttp) -> None:
    team = _setup(staff)
    _fake_coolify(fake_http)
    # Without read:sensitive, Coolify hides the key material.
    fake_http.on("GET", f"{C}/security/keys", [{"uuid": "k1", "name": "coolify"}])
    fake_http.on("GET", f"{C}/security/keys/k1", {"uuid": "k1", "name": "coolify"})

    job = _start(staff, team, "patch_check")
    assert job["status"] == "failed"
    assert "read:sensitive" in job["error"]


def test_image_scan_over_ssh(staff: TestClient, fake_http: FakeHttp, shell: FakeShell) -> None:
    team = _setup(staff)
    _fake_coolify(fake_http)
    fake_http.on("GET", f"{C}/security/keys", [{"uuid": "k1", "private_key": KEY}])
    report = {
        "matches": [
            {
                "vulnerability": {
                    "id": "CVE-1",
                    "severity": "Critical",
                    "fix": {"versions": ["1.2"]},
                },
                "artifact": {"name": "openssl", "version": "1.1"},
            },
            {
                "vulnerability": {"id": "CVE-2", "severity": "Medium", "fix": {"versions": []}},
                "artifact": {"name": "zlib", "version": "1.0"},
            },
        ]
    }
    shell.answers["docker ps"] = (0, "ssa-dev:latest\npostgres:16\n")
    shell.answers["anchore/grype"] = (0, json.dumps(report))

    job = _start(staff, team, "image_scan")
    assert job["status"] == "succeeded", job
    images = {i["image"]: i for i in job["result"]["images"]}
    assert set(images) == {"ssa-dev:latest", "postgres:16"}
    assert images["ssa-dev:latest"]["counts"]["critical"] == 1
    assert images["ssa-dev:latest"]["findings"][0]["id"] == "CVE-1"  # worst first


def test_one_job_at_a_time_per_server(staff: TestClient, fake_http: FakeHttp, db: Any) -> None:
    from app.modules.coolify.models import ServerJob

    team = _setup(staff)
    _fake_coolify(fake_http)
    db.add(ServerJob(team_id=team["id"], server_uuid="srv1", kind="patch_all", status="running"))
    db.commit()
    r = staff.post(
        f"/api/tools/coolify/teams/{team['id']}/servers/srv1/jobs", json={"kind": "patch_check"}
    )
    assert r.status_code == 409


def test_parse_apt_upgradable() -> None:
    updates = ssh.parse_apt_upgradable(APT_LIST)
    assert [(u.package, u.security) for u in updates] == [
        ("openssl", True),
        ("curl", False),
        ("libssl3", True),
    ]
    assert updates[0].current_version == "3.0.2-0ubuntu1.15"


def test_connect_needs_keys() -> None:
    with pytest.raises(ExternalServiceError, match="read:sensitive"):
        ssh.connect(ssh.SshTarget(host="203.0.113.2", port=22, user="root", private_keys=[]))


# --- connecting teams automatically ----------------------------------------------

ROOT_KEY = "-----BEGIN OPENSSH PRIVATE KEY-----\nroot\n-----END OPENSSH PRIVATE KEY-----\n"
COOLIFY_TEAMS = [
    {
        "id": 0,
        "name": "Root Team",
        "ips": ["host.docker.internal"],
        "admins": [{"id": 0, "email": "admin@cs.test", "role": "owner"}],
    },
    {
        "id": 3,
        "name": "Before Dawn Practicum Team",
        "ips": ["167.99.6.42"],
        "admins": [{"id": 0, "email": "admin@cs.test", "role": "owner"}],
    },
    {
        "id": 4,
        "name": "Leapfrog Practicum Team",
        "ips": ["142.93.198.79"],
        "admins": [{"id": 5, "email": "ta@cs.test", "role": "admin"}],
    },
]


def _decoded(text: str) -> str:
    """The first base64_decode('...') argument in a tinker command or script, decoded."""
    m = re.search(r"base64_decode\('([^']+)'\)", text)
    assert m is not None, text
    return base64.b64decode(m.group(1)).decode()


class FakeCoolifyServer(FakeShell):
    """The Coolify server: its container, its teams, and Coolify's createToken()."""

    def __init__(self) -> None:
        super().__init__({})
        self.created: list[dict[str, Any]] = []
        self.targets: list[ssh.SshTarget] = []

    def run(self, command: str, timeout: float = 300) -> tuple[int, str]:
        self.commands.append(command)
        if command.startswith("docker ps"):
            return 0, "coolify\n"
        if "artisan tinker" not in command:
            return 0, ""
        script = _decoded(command)
        if "createToken" not in script:
            return 0, f"WBJSON:{json.dumps(COOLIFY_TEAMS)}\n= null\n"
        data = json.loads(_decoded(script))
        self.created.append(data)
        token = f"7|made-for-team-{data['team_id']}"
        return 0, f"WBJSON:{json.dumps({'token': token})}\n= null\n"


@pytest.fixture
def coolify_server(monkeypatch: pytest.MonkeyPatch) -> FakeCoolifyServer:
    fake = FakeCoolifyServer()

    def connect(target: ssh.SshTarget) -> FakeCoolifyServer:
        fake.targets.append(target)
        return fake

    monkeypatch.setattr(ssh, "connect", connect)
    return fake


def _admin_setup(
    client: TestClient, fake: FakeHttp, team_name: str, droplet_label: str | None
) -> dict[str, Any]:
    client.put("/api/credentials/system/coolify_url", json={"value": "https://coolify.test"})
    client.put("/api/credentials/me/coolify_token", json={"value": "1|root-admin-token-xyz"})
    fake.on("GET", f"{C}/security/keys", [{"uuid": "k0", "private_key": ROOT_KEY}])
    links = (
        [{"service_id": "coolify", "url": "https://coolify.test", "label": droplet_label}]
        if droplet_label
        else []
    )
    r = client.post("/api/teams", json={"name": team_name, "links": links})
    assert r.status_code == 201, r.text
    team: dict[str, Any] = r.json()
    return team


def test_team_is_connected_automatically(
    staff: TestClient, fake_http: FakeHttp, coolify_server: FakeCoolifyServer
) -> None:
    team = _admin_setup(staff, fake_http, "Before Dawn", "BeforeDawn · 167.99.6.42")
    overview = staff.get(f"/api/tools/coolify/teams/{team['id']}/overview").json()
    assert overview["token_set"] is False
    assert overview["auto_connect"] is True

    r = staff.post(f"/api/tools/coolify/teams/{team['id']}/connect")
    assert r.status_code == 200, r.text
    assert r.json()["coolify_team"] == "Before Dawn Practicum Team"

    # It logged in to the Coolify server with Coolify's own key, as root.
    [target] = coolify_server.targets
    assert (target.host, target.user, list(target.private_keys)) == (
        "coolify.test",
        "root",
        [ROOT_KEY],
    )
    # ...and made a token for the right Coolify team, owned by one of its admins.
    [made] = coolify_server.created
    assert made == {
        "team_id": 3,
        "user_id": 0,
        "name": "course-workbench",
        "abilities": ["read", "read:sensitive", "write", "deploy"],
    }
    creds = staff.get(f"/api/teams/{team['id']}/credentials").json()
    assert next(c for c in creds if c["key"] == "coolify_team_token")["is_set"] is True


def test_teams_are_matched_by_name_when_there_is_no_droplet_link(
    staff: TestClient, fake_http: FakeHttp, coolify_server: FakeCoolifyServer
) -> None:
    team = _admin_setup(staff, fake_http, "Leapfrog", None)
    r = staff.post(f"/api/tools/coolify/teams/{team['id']}/connect")
    assert r.status_code == 200, r.text
    [made] = coolify_server.created
    assert (made["team_id"], made["user_id"]) == (4, 5)


def test_unknown_team_is_not_guessed(
    staff: TestClient, fake_http: FakeHttp, coolify_server: FakeCoolifyServer
) -> None:
    team = _admin_setup(staff, fake_http, "Root", None)  # must never match the root team
    r = staff.post(f"/api/tools/coolify/teams/{team['id']}/connect")
    assert r.status_code == 404
    assert "Couldn't tell which Coolify team" in r.json()["detail"]
    assert coolify_server.created == []


def test_auto_connect_needs_an_admin_token(staff: TestClient, fake_http: FakeHttp) -> None:
    staff.put("/api/credentials/system/coolify_url", json={"value": "https://coolify.test"})
    team = _create_team(staff, "Nimbus")
    assert (
        staff.get(f"/api/tools/coolify/teams/{team['id']}/overview").json()["auto_connect"] is False
    )
    r = staff.post(f"/api/tools/coolify/teams/{team['id']}/connect")
    assert r.status_code == 400
    assert "Coolify admin token" in r.json()["detail"]
    # Not having one doesn't make Coolify "not configured".
    status = staff.get("/api/tools/coolify/status").json()
    assert "coolify_token" not in status["missing_user_credentials"]


def test_auto_connect_explains_a_hidden_ssh_key(staff: TestClient, fake_http: FakeHttp) -> None:
    team = _admin_setup(staff, fake_http, "Before Dawn", "BeforeDawn · 167.99.6.42")
    fake_http.on("GET", f"{C}/security/keys", [{"uuid": "k0"}])
    fake_http.on("GET", f"{C}/security/keys/k0", {"uuid": "k0"})
    r = staff.post(f"/api/tools/coolify/teams/{team['id']}/connect")
    assert r.status_code == 502
    assert "main (root) Coolify team" in r.json()["detail"]


def test_course_summary_reads_every_team_and_is_cached(
    staff: TestClient, fake_http: FakeHttp, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.modules.coolify import service as coolify_service

    monkeypatch.setattr(coolify_service, "_summary_cache", {})
    _setup(staff, "Before Dawn")
    _create_team(staff, "Nimbus")  # not connected
    _fake_coolify(fake_http)
    fake_http.on(
        "GET",
        f"{C}/applications",
        [
            {
                "uuid": "app1",
                "name": "ssa dev",
                "status": "running:healthy",
                "git_repository": "https://github.com/org/ssa-portal.git",
            },
            {
                "uuid": "app2",
                "name": "ssa prod",
                "status": "exited:unhealthy",
                "git_repository": "org/ssa-portal",
            },
        ],
    )

    teams = {t["team_name"]: t for t in staff.get("/api/tools/coolify/summary").json()["teams"]}
    assert teams["Nimbus"]["connected"] is False
    bd = teams["Before Dawn"]
    assert {a["name"]: a["status"] for a in bd["apps"]} == {
        "ssa dev": "running:healthy",
        "ssa prod": "exited:unhealthy",
        "postgres": "running:healthy",
    }
    assert (
        next(a for a in bd["apps"] if a["name"] == "ssa dev")["security"]["status"] == "update_now"
    )
    assert bd["repos"] == ["org/ssa-portal"]
    assert [s["name"] for s in bd["servers"]] == ["before dawn server"]

    calls = len(fake_http.calls)
    staff.get("/api/tools/coolify/summary")  # cached for a minute
    assert len(fake_http.calls) == calls
    staff.get("/api/tools/coolify/summary", params={"refresh": True})
    assert len(fake_http.calls) > calls


def test_refused_logins_are_not_retried_right_away(
    staff: TestClient, fake_http: FakeHttp, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.modules.coolify import service as coolify_service

    monkeypatch.setattr(coolify_service, "_ssh_refusals", {})
    attempts: list[ssh.SshTarget] = []

    def refuse(target: ssh.SshTarget) -> FakeShell:
        attempts.append(target)
        raise ExternalServiceError("Couldn't log in to root@coolify.test with Coolify's SSH keys")

    monkeypatch.setattr(ssh, "connect", refuse)
    team = _admin_setup(staff, fake_http, "Before Dawn", "BeforeDawn · 167.99.6.42")
    url = f"/api/tools/coolify/teams/{team['id']}/connect"

    assert staff.post(url).status_code == 502
    second = staff.post(url)
    assert second.status_code == 502
    assert "Not retrying for a while" in second.json()["detail"]
    assert len(attempts) == 1  # the server was only knocked on once

    # A new admin token tries again straight away.
    staff.put("/api/credentials/me/coolify_token", json={"value": "1|a-new-root-team-token"})
    assert staff.post(url).status_code == 502
    assert len(attempts) == 2


def test_advanced_api_reads_for_anyone_writes_for_superusers(
    client: TestClient, fake_http: FakeHttp, make_user: Any, login: Any
) -> None:
    make_user("staff@example.com", is_superuser=True)
    make_user("ta@example.com")
    login("staff@example.com")
    team = _setup(client)
    url = f"/api/tools/coolify/teams/{team['id']}/api"
    fake_http.on("GET", f"{C}/databases/db1/backups", [{"uuid": "b1", "frequency": "0 0 * * *"}])
    fake_http.on(
        "POST",
        f"{C}/databases/db1/backups",
        http.HttpError(422, {"message": "frequency is required"}),
    )

    r = client.post(url, json={"path": "/api/v1/databases/db1/backups"})
    assert r.json() == {"status": 200, "data": [{"uuid": "b1", "frequency": "0 0 * * *"}]}
    # Coolify's own errors come back as they are, for the person to read.
    r = client.post(url, json={"method": "POST", "path": "databases/db1/backups", "body": {}})
    assert r.json() == {"status": 422, "data": {"message": "frequency is required"}}
    assert client.post(url, json={"path": "/../../etc"}).status_code == 422
    assert client.post(url, json={"path": "https://evil.test/x"}).status_code == 422

    login("ta@example.com")
    assert client.post(url, json={"path": "/databases/db1/backups"}).json()["status"] == 200
    r = client.post(url, json={"method": "DELETE", "path": "/databases/db1"})
    assert r.status_code == 403
