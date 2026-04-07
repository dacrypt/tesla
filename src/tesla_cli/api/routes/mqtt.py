"""MQTT API routes: /api/mqtt/*"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from tesla_cli.core.config import load_config

router = APIRouter()


@router.get("/status")
def mqtt_status() -> dict:
    """MQTT broker connection status."""
    cfg = load_config()
    mc = cfg.mqtt
    configured = bool(mc.broker)

    result: dict = {
        "broker": mc.broker or None,
        "port": mc.port,
        "configured": configured,
        "topic_prefix": mc.topic_prefix or "tesla",
        "tls": mc.tls,
        "username_set": bool(mc.username),
    }

    if configured:
        try:
            import paho.mqtt.client as mqtt  # type: ignore[import]

            client = mqtt.Client(client_id="tesla-cli-api-status", protocol=mqtt.MQTTv311)
            if mc.username:
                client.username_pw_set(mc.username, mc.password or "")
            if mc.tls:
                client.tls_set()
            client.connect(mc.broker, mc.port, keepalive=5)
            client.disconnect()
            result["connectivity"] = "ok"
        except ImportError:
            result["connectivity"] = "paho-mqtt not installed"
        except Exception as exc:  # noqa: BLE001
            result["connectivity"] = f"error: {exc}"

    return result


class PublishRequest(BaseModel):
    topic: str
    payload: str


@router.post("/publish")
def mqtt_publish(body: PublishRequest) -> dict:
    """Publish a message to MQTT broker."""
    cfg = load_config()
    if not cfg.mqtt.broker:
        raise HTTPException(
            status_code=400,
            detail="MQTT not configured. Run: tesla mqtt setup <BROKER>",
        )

    try:
        import paho.mqtt.client as mqtt  # type: ignore[import]
    except ImportError:
        raise HTTPException(
            status_code=501,
            detail="paho-mqtt not installed. Run: pip install paho-mqtt",
        )

    try:
        mc = cfg.mqtt
        client = mqtt.Client(client_id="tesla-cli-api-publish", protocol=mqtt.MQTTv311)
        if mc.username:
            client.username_pw_set(mc.username, mc.password or "")
        if mc.tls:
            client.tls_set()
        client.connect(mc.broker, mc.port, keepalive=10)
        client.publish(body.topic, body.payload, qos=mc.qos)
        client.loop(timeout=0.5)
        client.disconnect()
        return {"ok": True, "topic": body.topic, "broker": mc.broker}
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))
