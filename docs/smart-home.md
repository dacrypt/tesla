# Smart home: HomeKit, Google Home, Alexa, Shortcuts, IFTTT

tesla-cli has no cloud of its own, so voice assistants and smart-home hubs
reach your car through the self-hosted REST API. There are two routes:

| You use | Route |
|---------|-------|
| **Home Assistant** | Sensors via `tesla ha sync` or MQTT discovery; actions via `rest_command`. HA then exposes them to **HomeKit** (HomeKit Bridge), **Google Home** and **Alexa** (Nabu Casa or the manual integrations). |
| **No hub** | Call the API directly from **Apple Shortcuts**, **IFTTT Webhooks**, Tasker, or `curl`. |

Read [self-hosting.md → Remote access](self-hosting.md#3-remote-access) first:
the hub or phone must reach the API over your LAN, a VPN (Tailscale) or a
reverse proxy with HTTPS. Never port-forward it.

## Keys and safety

- Every request carries the `X-API-Key` header. Query-string keys are refused.
- Use the **read-only key** (`tesla serve api-key --read-only --rotate`) for
  anything that only reads state (dashboards, HA sensors). It can't send commands.
- Give the **full key** only to hubs that must send commands, and store it in
  the hub's secret store (HA `secrets.yaml`, Shortcuts "Text" action on-device).
- Unlock and trunk commands from a voice assistant are risky. Consider exposing
  only lock, climate and charging. Every command is written to the audit log
  (`GET /api/audit`).
- A sleeping car answers `503`. Send `POST /api/vehicle/wake` first, or retry.

## Endpoints you will use

| Action | Request |
|--------|---------|
| Wake | `POST /api/vehicle/wake` |
| Lock / unlock | `POST /api/security/lock` · `POST /api/security/unlock` |
| Sentry on / off | `POST /api/security/sentry/on` · `POST /api/security/sentry/off` |
| Climate on / off | `POST /api/climate/on` · `POST /api/climate/off` |
| Cabin temperature | `POST /api/climate/temp` body `{"driver_temp": 21}` |
| Start / stop charging | `POST /api/charge/start` · `POST /api/charge/stop` |
| Charge limit | `POST /api/charge/limit` body `{"percent": 80}` |
| Run a scene | `POST /api/scenes/{scene_id}/execute` (list them with `GET /api/scenes/`) |
| Battery, range, lock state… | `GET /api/vehicle/summary` |
| Compact status (for widgets) | `GET /api/vehicle/status-line` |

Full reference: [api-reference.md](api-reference.md).

## Home Assistant

**State.** Either push sensors with `tesla ha setup <url> <token>` and then
`tesla ha sync`, or publish to MQTT with HA auto-discovery (`tesla mqtt setup`, then
`tesla mqtt ha-discovery`).
See the [user guide](user-guide.md).

**Actions.** Add `rest_command`s and wrap them in scripts, which HA can
expose to HomeKit, Google and Alexa:

```yaml
# configuration.yaml
rest_command:
  tesla_climate_on:
    url: "http://tesla-cli.lan:8080/api/climate/on"
    method: post
    headers:
      X-API-Key: !secret tesla_cli_api_key
  tesla_lock:
    url: "http://tesla-cli.lan:8080/api/security/lock"
    method: post
    headers:
      X-API-Key: !secret tesla_cli_api_key
  tesla_charge_limit:
    url: "http://tesla-cli.lan:8080/api/charge/limit"
    method: post
    headers:
      X-API-Key: !secret tesla_cli_api_key
    content_type: "application/json"
    payload: '{"percent": {{ percent }}}'

script:
  tesla_precondition:
    alias: "Precondition the car"
    sequence:
      - action: rest_command.tesla_climate_on
```

Then expose `script.tesla_precondition` through **HomeKit Bridge** (it shows
up as a switch: "Hey Siri, turn on Precondition the car"), or through the
Google Assistant or Alexa integration.

## Apple Shortcuts

1. **Get Contents of URL** → `http://tesla-cli.lan:8080/api/climate/on`
2. Method **POST**, header `X-API-Key` = your full key.
3. Optionally add **Get Dictionary Value** on the response and **Show Result**.

To read data, use **GET** on `/api/vehicle/status-line` with the read-only key,
then pick fields (battery, lock, temperature) with **Get Dictionary Value**.

## IFTTT and other webhook services

IFTTT's *Webhooks → Make a web request* action can call the API directly.
URL `https://tesla.example.com/api/charge/start`, method `POST`, content type
`application/json`, additional header `X-API-Key: <full key>`. This only works
if your API is reachable over HTTPS through a reverse proxy or a Cloudflare
Tunnel. Keep Cloudflare Access or similar in front of it. If you'd rather not
expose the API at all, use Home Assistant instead.

## curl (for testing)

```bash
curl -fsS -X POST -H "X-API-Key: $TESLA_API_KEY" http://localhost:8080/api/vehicle/wake
```

```bash
curl -fsS -X POST -H "X-API-Key: $TESLA_API_KEY" -H "Content-Type: application/json" \
  -d '{"percent": 80}' http://localhost:8080/api/charge/limit
```
