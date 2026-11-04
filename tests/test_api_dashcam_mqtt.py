"""Tests for /api/dashcam/* and /api/mqtt/* routes.

Dashcam: the allowed USB mount prefixes are widened to include tmp_path so a
fake TeslaCam tree can be built without touching /Volumes, /mnt or /media.
MQTT: paho-mqtt is optional; a fake ``paho.mqtt.client`` module is injected.
"""

from __future__ import annotations

import sys
import types
from unittest.mock import MagicMock, patch

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from tesla_cli.api.app import create_app  # noqa: E402
from tesla_cli.api.routes import dashcam  # noqa: E402
from tesla_cli.core.config import Config  # noqa: E402


@pytest.fixture(scope="module")
def client():
    with patch("tesla_cli.api.app.load_config", return_value=Config()):
        app = create_app(vin=None)
    return TestClient(app, raise_server_exceptions=False)


# ── Dashcam ─────────────────────────────────────────────────────────────────


@pytest.fixture
def usb(tmp_path, monkeypatch):
    root = (tmp_path / "TESLADRIVE").resolve()
    monkeypatch.setattr(
        dashcam, "_ALLOWED_USB_PREFIXES", (*dashcam._ALLOWED_USB_PREFIXES, str(tmp_path.resolve()))
    )
    return root


def _clip(path, size: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"\0" * size)


@pytest.mark.parametrize(
    "n,expected",
    [(0, "0 B"), (1023, "1023 B"), (1024, "1 KB"), (5 * 1024**2, "5 MB"), (3 * 1024**3, "3 GB")],
)
def test_human_size(n, expected):
    assert dashcam._human_size(n) == expected


def test_human_size_terabytes():
    assert dashcam._human_size(2 * 1024**4) == "2 TB"


@pytest.mark.parametrize("path", ["/etc", "/mnt/../etc/passwd", "relative/dir", "/mntx/usb"])
def test_paths_outside_allowed_prefixes_rejected(client, path):
    for ep in ("status", "clips"):
        r = client.get(f"/api/dashcam/{ep}", params={"usb_path": path})
        assert r.status_code == 400
        assert "/Volumes/" in r.json()["detail"]


def test_status_not_mounted(client):
    r = client.get("/api/dashcam/status", params={"usb_path": "/mnt/does-not-exist-xyz"})
    assert r.status_code == 200
    assert r.json() == {
        "usb_path": "/mnt/does-not-exist-xyz",
        "mounted": False,
        "teslacam_found": False,
        "subdirs": {},
    }


def test_status_mounted_with_subdirs(client, usb):
    (usb / "TeslaCam" / "SavedClips").mkdir(parents=True)
    (usb / "TeslaCam" / "RecentClips").mkdir()
    body = client.get("/api/dashcam/status", params={"usb_path": str(usb)}).json()
    assert body["mounted"] is True
    assert body["teslacam_found"] is True
    assert body["subdirs"] == {"SavedClips": True, "SentryClips": False, "RecentClips": True}


def test_status_mounted_without_teslacam(client, usb):
    usb.mkdir()
    body = client.get("/api/dashcam/status", params={"usb_path": str(usb)}).json()
    assert body["mounted"] is True
    assert body["teslacam_found"] is False


def test_clips_missing_teslacam_404(client, usb):
    usb.mkdir()
    r = client.get("/api/dashcam/clips", params={"usb_path": str(usb)})
    assert r.status_code == 404
    assert "TeslaCam directory not found" in r.json()["detail"]


def test_clips_listing(client, usb):
    tc = usb / "TeslaCam"
    _clip(tc / "SavedClips" / "2026-01-01_10-00-00" / "front.mp4", 2048)
    _clip(tc / "SavedClips" / "2026-01-01_10-00-00" / "back.mp4", 1024)
    _clip(tc / "SavedClips" / "2026-02-01_09-00-00" / "front.mp4", 10)
    _clip(tc / "SavedClips" / "2026-02-01_09-00-00" / "event.json", 10)  # not mp4
    (tc / "SavedClips" / "2026-03-01_empty").mkdir()
    _clip(tc / "SentryClips" / "2026-01-15_12-00-00" / "left.mp4", 3 * 1024**2)
    # RecentClips without date dirs: flat mp4 files
    _clip(tc / "RecentClips" / "a.mp4", 100)
    _clip(tc / "RecentClips" / "b.mp4", 200)

    clips = client.get("/api/dashcam/clips", params={"usb_path": str(usb)}).json()
    assert clips == [
        {
            "type": "saved",
            "date": "2026-02-01_09-00-00",
            "file_count": 1,
            "size_bytes": 10,
            "size_human": "10 B",
        },
        {
            "type": "saved",
            "date": "2026-01-01_10-00-00",
            "file_count": 2,
            "size_bytes": 3072,
            "size_human": "3 KB",
        },
        {
            "type": "sentry",
            "date": "2026-01-15_12-00-00",
            "file_count": 1,
            "size_bytes": 3 * 1024**2,
            "size_human": "3 MB",
        },
        {
            "type": "recent",
            "date": "RecentClips",
            "file_count": 2,
            "size_bytes": 300,
            "size_human": "300 B",
        },
    ]


def test_clips_flat_dir_without_mp4_is_skipped(client, usb):
    (usb / "TeslaCam" / "RecentClips").mkdir(parents=True)
    (usb / "TeslaCam" / "RecentClips" / "readme.txt").write_text("x")
    assert client.get("/api/dashcam/clips", params={"usb_path": str(usb)}).json() == []


# ── MQTT ────────────────────────────────────────────────────────────────────


def _mqtt_cfg(**kw) -> Config:
    cfg = Config()
    for k, v in kw.items():
        setattr(cfg.mqtt, k, v)
    return cfg


@pytest.fixture
def fake_paho(monkeypatch):
    client_inst = MagicMock()
    mod = types.ModuleType("paho.mqtt.client")
    mod.MQTTv311 = 4
    mod.Client = MagicMock(return_value=client_inst)
    paho = types.ModuleType("paho")
    paho_mqtt = types.ModuleType("paho.mqtt")
    paho.mqtt = paho_mqtt
    paho_mqtt.client = mod
    monkeypatch.setitem(sys.modules, "paho", paho)
    monkeypatch.setitem(sys.modules, "paho.mqtt", paho_mqtt)
    monkeypatch.setitem(sys.modules, "paho.mqtt.client", mod)
    return mod, client_inst


@pytest.fixture
def no_paho(monkeypatch):
    # None in sys.modules makes `import` raise ImportError.
    monkeypatch.setitem(sys.modules, "paho", None)
    monkeypatch.setitem(sys.modules, "paho.mqtt", None)
    monkeypatch.setitem(sys.modules, "paho.mqtt.client", None)


def _with_cfg(cfg):
    return patch("tesla_cli.api.routes.mqtt.load_config", return_value=cfg)


def test_mqtt_status_unconfigured(client, fake_paho):
    with _with_cfg(_mqtt_cfg(broker="")):
        body = client.get("/api/mqtt/status").json()
    assert body["configured"] is False
    assert body["broker"] is None
    assert body["topic_prefix"] == "tesla"
    assert body["port"] == 1883
    assert body["username_set"] is False
    assert "connectivity" not in body
    fake_paho[0].Client.assert_not_called()


def test_mqtt_status_connectivity_ok(client, fake_paho):
    mod, inst = fake_paho
    cfg = _mqtt_cfg(broker="mqtt.local", port=8883, username="u", password="p", tls=True)
    with _with_cfg(cfg):
        body = client.get("/api/mqtt/status").json()
    assert body["configured"] is True
    assert body["broker"] == "mqtt.local"
    assert body["port"] == 8883
    assert body["tls"] is True
    assert body["username_set"] is True
    assert body["connectivity"] == "ok"
    inst.username_pw_set.assert_called_once_with("u", "p")
    inst.tls_set.assert_called_once()
    inst.connect.assert_called_once_with("mqtt.local", 8883, keepalive=5)
    inst.disconnect.assert_called_once()


def test_mqtt_status_connect_error(client, fake_paho):
    _, inst = fake_paho
    inst.connect.side_effect = OSError("refused")
    with _with_cfg(_mqtt_cfg(broker="mqtt.local")):
        body = client.get("/api/mqtt/status").json()
    assert body["connectivity"] == "error: refused"
    inst.username_pw_set.assert_not_called()
    inst.tls_set.assert_not_called()


def test_mqtt_status_paho_missing(client, no_paho):
    with _with_cfg(_mqtt_cfg(broker="mqtt.local")):
        body = client.get("/api/mqtt/status").json()
    assert body["connectivity"] == "paho-mqtt not installed"


def test_mqtt_publish_unconfigured_400(client, fake_paho):
    with _with_cfg(_mqtt_cfg(broker="")):
        r = client.post("/api/mqtt/publish", json={"topic": "t", "payload": "p"})
    assert r.status_code == 400
    assert "not configured" in r.json()["detail"]


def test_mqtt_publish_paho_missing_501(client, no_paho):
    with _with_cfg(_mqtt_cfg(broker="mqtt.local")):
        r = client.post("/api/mqtt/publish", json={"topic": "t", "payload": "p"})
    assert r.status_code == 501


def test_mqtt_publish_ok(client, fake_paho):
    _, inst = fake_paho
    cfg = _mqtt_cfg(broker="mqtt.local", port=1883, qos=1, username="u", tls=True)
    with _with_cfg(cfg):
        r = client.post("/api/mqtt/publish", json={"topic": "tesla/x", "payload": "hello"})
    assert r.status_code == 200
    assert r.json() == {"ok": True, "topic": "tesla/x", "broker": "mqtt.local"}
    inst.username_pw_set.assert_called_once_with("u", "")
    inst.connect.assert_called_once_with("mqtt.local", 1883, keepalive=10)
    inst.publish.assert_called_once_with("tesla/x", "hello", qos=1)
    inst.disconnect.assert_called_once()


def test_mqtt_publish_broker_error_502(client, fake_paho):
    _, inst = fake_paho
    inst.publish.side_effect = RuntimeError("not authorised")
    with _with_cfg(_mqtt_cfg(broker="mqtt.local")):
        r = client.post("/api/mqtt/publish", json={"topic": "t", "payload": "p"})
    assert r.status_code == 502
    assert r.json()["detail"] == "not authorised"


def test_mqtt_publish_validates_body(client, fake_paho):
    with _with_cfg(_mqtt_cfg(broker="mqtt.local")):
        assert client.post("/api/mqtt/publish", json={"topic": "t"}).status_code == 422
