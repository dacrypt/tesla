"""Tests for the TeslaMate managed Docker Compose stack orchestration."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

from tesla_cli.infra.teslamate_stack import TeslaMateStack, COMPOSE_TEMPLATE
from tesla_cli.core.exceptions import DockerNotFoundError, TeslaMateStackError


@pytest.fixture
def stack_dir(tmp_path):
    return tmp_path / "teslamate"


@pytest.fixture
def stack(stack_dir):
    return TeslaMateStack(stack_dir)


# ── Docker checks ────────────────────────────────────────────────────────────


class TestDockerChecks:
    def test_check_docker_not_installed(self, stack):
        with patch("subprocess.run", side_effect=FileNotFoundError):
            with pytest.raises(DockerNotFoundError, match="Install Docker"):
                stack.check_docker()

    def test_check_docker_daemon_not_running(self, stack):
        with patch("subprocess.run", return_value=MagicMock(returncode=1)):
            with pytest.raises(DockerNotFoundError, match="daemon is not running"):
                stack.check_docker()

    def test_check_docker_ok(self, stack):
        with patch("subprocess.run", return_value=MagicMock(returncode=0)):
            stack.check_docker()  # should not raise

    def test_check_docker_compose_not_found(self, stack):
        with patch("subprocess.run", return_value=MagicMock(returncode=1, stdout="")):
            with pytest.raises(DockerNotFoundError, match="compose.*plugin"):
                stack.check_docker_compose()

    def test_check_docker_compose_ok(self, stack):
        with patch("subprocess.run", return_value=MagicMock(returncode=0, stdout="2.27.0\n")):
            version = stack.check_docker_compose()
            assert version == "2.27.0"


# ── Port checks ──────────────────────────────────────────────────────────────


class TestPortChecks:
    def test_port_not_in_use(self, stack):
        with patch("socket.socket") as mock_socket:
            mock_socket.return_value.__enter__ = MagicMock(return_value=mock_socket.return_value)
            mock_socket.return_value.__exit__ = MagicMock(return_value=False)
            mock_socket.return_value.connect_ex.return_value = 1  # refused = free
            assert not stack.port_in_use(5432)

    def test_port_in_use(self, stack):
        with patch("socket.socket") as mock_socket:
            mock_socket.return_value.__enter__ = MagicMock(return_value=mock_socket.return_value)
            mock_socket.return_value.__exit__ = MagicMock(return_value=False)
            mock_socket.return_value.connect_ex.return_value = 0  # connected = in use
            assert stack.port_in_use(5432)

    def test_check_ports_finds_conflicts(self, stack):
        def fake_connect_ex(addr):
            return 0 if addr[1] == 3000 else 1

        with patch("socket.socket") as mock_socket:
            mock_socket.return_value.__enter__ = MagicMock(return_value=mock_socket.return_value)
            mock_socket.return_value.__exit__ = MagicMock(return_value=False)
            mock_socket.return_value.connect_ex.side_effect = fake_connect_ex
            conflicts = stack.check_ports(5432, 3000, 4000, 1883)
            assert len(conflicts) == 1
            assert conflicts[0] == ("Grafana", 3000)


# ── Compose template ─────────────────────────────────────────────────────────


class TestComposeTemplate:
    def test_template_has_all_services(self):
        assert "postgres:" in COMPOSE_TEMPLATE
        assert "teslamate:" in COMPOSE_TEMPLATE
        assert "grafana:" in COMPOSE_TEMPLATE
        assert "mosquitto:" in COMPOSE_TEMPLATE

    def test_template_has_volumes(self):
        assert "teslamate-db:" in COMPOSE_TEMPLATE
        assert "teslamate-grafana-data:" in COMPOSE_TEMPLATE

    def test_template_has_env_variables(self):
        assert "${TM_DB_PASSWORD}" in COMPOSE_TEMPLATE
        assert "${TM_PORT:-4000}" in COMPOSE_TEMPLATE
        assert "${TM_GRAFANA_PORT:-3000}" in COMPOSE_TEMPLATE
        assert "${TM_MQTT_PORT:-1883}" in COMPOSE_TEMPLATE

    def test_template_has_healthcheck(self):
        assert "pg_isready" in COMPOSE_TEMPLATE
        assert "service_healthy" in COMPOSE_TEMPLATE


# ── Installation ─────────────────────────────────────────────────────────────


class TestInstall:
    @patch("tesla_cli.infra.teslamate_stack.TeslaMateStack._wait_healthy", return_value=True)
    @patch("subprocess.run", return_value=MagicMock(returncode=0, stdout="2.27.0\n"))
    @patch("tesla_cli.infra.teslamate_stack.get_token", return_value=None)
    @patch("tesla_cli.infra.teslamate_stack.set_token")
    @patch("tesla_cli.infra.teslamate_stack.has_token", return_value=False)
    def test_install_creates_files(self, _ht, _st, _gt, mock_run, _wh, stack, stack_dir):
        result = stack.install()

        assert stack_dir.exists()
        assert (stack_dir / "docker-compose.yml").exists()
        assert (stack_dir / ".env").exists()

        env_content = (stack_dir / ".env").read_text()
        assert "TM_DB_PASSWORD=" in env_content
        assert "TM_ENCRYPTION_KEY=" in env_content
        assert "TM_GRAFANA_PASSWORD=" in env_content

        assert result["healthy"] is True
        assert "postgresql://teslamate:" in result["database_url"]
        assert result["postgres_port"] == 5432
        assert result["grafana_port"] == 3000

    @patch("tesla_cli.infra.teslamate_stack.TeslaMateStack._wait_healthy", return_value=True)
    @patch("subprocess.run", return_value=MagicMock(returncode=0, stdout="2.27.0\n"))
    @patch("tesla_cli.infra.teslamate_stack.get_token", return_value=None)
    @patch("tesla_cli.infra.teslamate_stack.set_token")
    @patch("tesla_cli.infra.teslamate_stack.has_token", return_value=False)
    def test_install_custom_ports(self, _ht, _st, _gt, mock_run, _wh, stack, stack_dir):
        result = stack.install(
            postgres_port=5433,
            grafana_port=3001,
            teslamate_port=4001,
            mqtt_port=1884,
        )

        env = (stack_dir / ".env").read_text()
        assert "TM_DB_PORT=5433" in env
        assert "TM_GRAFANA_PORT=3001" in env
        assert "TM_PORT=4001" in env
        assert "TM_MQTT_PORT=1884" in env
        assert result["postgres_port"] == 5433

    @patch("tesla_cli.infra.teslamate_stack.TeslaMateStack._wait_healthy", return_value=True)
    @patch("subprocess.run", return_value=MagicMock(returncode=0, stdout="2.27.0\n"))
    @patch("tesla_cli.infra.teslamate_stack.get_token")
    @patch("tesla_cli.infra.teslamate_stack.set_token")
    @patch("tesla_cli.infra.teslamate_stack.has_token", return_value=False)
    def test_install_includes_tesla_tokens(self, _ht, _st, mock_gt, mock_run, _wh, stack, stack_dir):
        def token_lookup(key):
            return {
                "fleet-access-token": "access123",
                "fleet-refresh-token": "refresh456",
            }.get(key)

        mock_gt.side_effect = token_lookup

        result = stack.install()
        env = (stack_dir / ".env").read_text()
        # Tokens are synced via RPC now, not env vars. Check client_id is in .env instead.
        assert "TM_TESLA_CLIENT_ID=" in env
        assert result["has_tesla_tokens"] is True

    def test_install_already_installed_no_force(self, stack, stack_dir):
        stack_dir.mkdir(parents=True)
        (stack_dir / "docker-compose.yml").write_text("exists")

        with pytest.raises(TeslaMateStackError, match="already installed"):
            stack.install()

    @patch("tesla_cli.infra.teslamate_stack.TeslaMateStack._wait_healthy", return_value=True)
    @patch("subprocess.run", return_value=MagicMock(returncode=0, stdout="2.27.0\n"))
    @patch("tesla_cli.infra.teslamate_stack.get_token", return_value=None)
    @patch("tesla_cli.infra.teslamate_stack.set_token")
    @patch("tesla_cli.infra.teslamate_stack.has_token", return_value=False)
    def test_install_env_permissions(self, _ht, _st, _gt, mock_run, _wh, stack, stack_dir):
        stack.install()
        import stat
        mode = (stack_dir / ".env").stat().st_mode
        assert mode & 0o077 == 0  # no group/other permissions


# ── Lifecycle ────────────────────────────────────────────────────────────────


class TestLifecycle:
    @pytest.fixture(autouse=True)
    def _setup(self, stack, stack_dir):
        stack_dir.mkdir(parents=True, exist_ok=True)
        (stack_dir / "docker-compose.yml").write_text("services: {}")
        self.stack = stack
        self.stack_dir = stack_dir

    def test_is_installed(self):
        assert self.stack.is_installed()

    def test_not_installed(self, tmp_path):
        s = TeslaMateStack(tmp_path / "nope")
        assert not s.is_installed()

    @patch("tesla_cli.infra.teslamate_stack.TeslaMateStack._wait_healthy", return_value=True)
    @patch("subprocess.run", return_value=MagicMock(returncode=0))
    def test_start(self, mock_run, _wh):
        self.stack.start()
        # Should have called docker compose up -d
        calls = [c for c in mock_run.call_args_list if "up" in c[0][0]]
        assert len(calls) > 0

    @patch("subprocess.run", return_value=MagicMock(returncode=0))
    def test_stop(self, mock_run):
        self.stack.stop()
        calls = [c for c in mock_run.call_args_list if "stop" in c[0][0]]
        assert len(calls) > 0

    @patch("tesla_cli.infra.teslamate_stack.TeslaMateStack._wait_healthy", return_value=True)
    @patch("subprocess.run", return_value=MagicMock(returncode=0))
    def test_restart(self, mock_run, _wh):
        self.stack.restart()

    @patch("tesla_cli.infra.teslamate_stack.TeslaMateStack._wait_healthy", return_value=True)
    @patch("subprocess.run", return_value=MagicMock(returncode=0, stdout="Pulling...\n"))
    def test_update(self, mock_run, _wh):
        output = self.stack.update()
        assert isinstance(output, str)

    def test_start_not_installed_raises(self, tmp_path):
        s = TeslaMateStack(tmp_path / "nope")
        with pytest.raises(TeslaMateStackError, match="not installed"):
            s.start()


# ── Status ───────────────────────────────────────────────────────────────────


class TestStatus:
    @pytest.fixture(autouse=True)
    def _setup(self, stack, stack_dir):
        stack_dir.mkdir(parents=True, exist_ok=True)
        (stack_dir / "docker-compose.yml").write_text("services: {}")
        self.stack = stack

    def test_status_parses_json(self):
        ps_output = "\n".join([
            json.dumps({"Service": "postgres", "State": "running", "Status": "Up 2 hours", "Image": "postgres:16", "Ports": "0.0.0.0:5432->5432/tcp"}),
            json.dumps({"Service": "teslamate", "State": "running", "Status": "Up 2 hours", "Image": "teslamate/teslamate:latest", "Ports": "0.0.0.0:4000->4000/tcp"}),
            json.dumps({"Service": "grafana", "State": "running", "Status": "Up 2 hours", "Image": "teslamate/grafana:latest", "Ports": "0.0.0.0:3000->3000/tcp"}),
            json.dumps({"Service": "mosquitto", "State": "running", "Status": "Up 2 hours", "Image": "eclipse-mosquitto:2", "Ports": "0.0.0.0:1883->1883/tcp"}),
        ])

        with patch("subprocess.run", return_value=MagicMock(returncode=0, stdout=ps_output)):
            services = self.stack.status()

        assert len(services) == 4
        assert services[0]["name"] == "postgres"
        assert services[0]["state"] == "running"

    def test_is_running_true(self):
        ps_output = json.dumps({"Service": "teslamate", "State": "running", "Status": "Up"})
        with patch("subprocess.run", return_value=MagicMock(returncode=0, stdout=ps_output)):
            assert self.stack.is_running()

    def test_is_running_false_no_containers(self):
        with patch("subprocess.run", return_value=MagicMock(returncode=0, stdout="")):
            assert not self.stack.is_running()

    def test_health_check_map(self):
        ps_output = "\n".join([
            json.dumps({"Service": "postgres", "State": "running"}),
            json.dumps({"Service": "teslamate", "State": "exited"}),
        ])
        with patch("subprocess.run", return_value=MagicMock(returncode=0, stdout=ps_output)):
            health = self.stack.health_check()
            assert health["postgres"] is True
            assert health["teslamate"] is False

    def test_status_empty_when_not_installed(self, tmp_path):
        s = TeslaMateStack(tmp_path / "nope")
        assert s.status() == []


# ── Uninstall ────────────────────────────────────────────────────────────────


class TestUninstall:
    @pytest.fixture(autouse=True)
    def _setup(self, stack, stack_dir):
        stack_dir.mkdir(parents=True, exist_ok=True)
        (stack_dir / "docker-compose.yml").write_text("services: {}")
        self.stack = stack

    @patch("subprocess.run", return_value=MagicMock(returncode=0))
    def test_uninstall_without_volumes(self, mock_run):
        self.stack.uninstall()
        cmd = mock_run.call_args[0][0]
        assert "down" in cmd
        assert "-v" not in cmd

    @patch("subprocess.run", return_value=MagicMock(returncode=0))
    def test_uninstall_with_volumes(self, mock_run):
        self.stack.uninstall(remove_volumes=True)
        cmd = mock_run.call_args[0][0]
        assert "-v" in cmd


# ── Exception classes ────────────────────────────────────────────────────────


class TestExceptions:
    def test_docker_not_found_error(self):
        err = DockerNotFoundError("custom detail")
        assert "custom detail" in str(err)

    def test_docker_not_found_error_no_detail(self):
        err = DockerNotFoundError()
        assert "Docker is required" in str(err)

    def test_teslamate_stack_error(self):
        err = TeslaMateStackError("stack broken")
        assert "stack broken" in str(err)
