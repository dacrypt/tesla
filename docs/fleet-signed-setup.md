# Vehicle Command Protocol (VCP) — complete setup

End-to-end walkthrough to go from **zero** to **`tesla vehicle flash-lights`
returns OK** on firmware 2024.26+. Expect 15–30 min the first time.

## Why this exists

Firmware `2024.26` and later reject unsigned Fleet API commands with
`HTTP 403 "Tesla Vehicle Command Protocol required"`. To control any
modern Tesla through the Fleet API you MUST sign commands with a
private key the vehicle trusts. Tesla-cli ships the crypto (via
`tesla-fleet-api`) — you provide the key pair and the hosting.

## Mental model

```
┌──────────────────────┐       ┌────────────────────────┐
│ developer.tesla.com  │◀──1──▶│   Fleet API app        │
│ your account         │       │   client_id + secret   │
└──────────────────────┘       │   Allowed Origin: host │
                               └────────────────────────┘
                                          │
                                          │ 2. register_partner()
                                          ▼
                               ┌────────────────────────┐
┌──────────────────────┐       │   Tesla caches YOUR    │
│ your-host.github.io  │───3──▶│   public key by domain │
│  .well-known/        │       └────────────────────────┘
│  com.tesla.3p.pub... │                  │
└──────────────────────┘                  │ 4. tesla.com/_ak/host
                                          ▼
                               ┌────────────────────────┐
                               │ Tesla app → Add Key    │
                               │ vehicle owner confirms │
                               └────────────────────────┘
                                          │
                                          │ 5. tesla vehicle X
                                          ▼
                               signed command → vehicle ✅
```

## One-time checklist

Run top-to-bottom. **Step 7 is the gotcha — don't skip it even if
steps 1–6 succeeded previously.**

| # | What | Where |
|---|------|-------|
| 1 | Create a Tesla Developer app | [developer.tesla.com](https://developer.tesla.com) |
| 2 | Create a GitHub Pages site | [github.com/new](https://github.com/new) |
| 3 | `tesla config auth fleet` | terminal |
| 4 | `tesla config auth fleet-signed` — generates local key pair | terminal |
| 5 | Publish the NEW `public-key.pem` on your host | your-host repo |
| 6 | **Re-register partner** to refresh Tesla's cached pubkey | terminal |
| 7 | Visit `https://tesla.com/_ak/<your-host>` in Safari on your iPhone | iPhone |
| 8 | Tap Add Key → Face ID → confirm | Tesla app |
| 9 | `tesla config set backend fleet-signed` | terminal |
| 10 | `tesla vehicle flash-lights` | terminal |

---

## 1. Create the Tesla Developer app

1. Sign in to [developer.tesla.com](https://developer.tesla.com) with
   your Tesla account. Go to **Create App**.
2. Fill in the form:

| Field | Value |
|-------|-------|
| Application Name | alphanumeric — Tesla **rejects dashes** (e.g. `CarMonitor`, `My Tesla Dashboard`) |
| Application Description | `Personal CLI dashboard for my Tesla` (or similar, under 150 chars) |
| Purpose of Usage | `Personal use — read my own vehicle state + control commands via CLI` |
| OAuth Grant Type | **Authorization Code and Machine-to-Machine** |
| Allowed Origin URL(s) | `https://<your-username>.github.io` (or your custom domain) |
| Allowed Redirect URI(s) | `https://auth.tesla.com/void/callback` |
| Allowed Returned URL(s) | `https://auth.tesla.com/void/callback` |
| Scopes (check all) | `vehicle_device_data`, `vehicle_location`, `vehicle_cmds`, `vehicle_charging_cmds`. Optional: `user_data`, `energy_device_data`, `energy_cmds` |

3. Submit and copy the **Client ID** (UUID) and **Client Secret** —
   you'll paste them into the CLI in step 3. Keep them somewhere safe
   (a password manager).

## 2. Create your hosting site on GitHub Pages

Every GitHub user gets one free personal Pages site at
`<username>.github.io`. Create the repo **once** (empty is fine for
now):

```bash
gh repo create <your-username>.github.io --public --clone
cd <your-username>.github.io
echo "# Tesla VCP public key hosting" > README.md
mkdir -p .well-known/appspecific
git add . && git commit -m "init" && git push
```

Enable Pages if it wasn't auto-enabled:

```bash
gh repo edit --enable-pages --pages-branch main
```

> ⚠ **Never publish someone else's pubkey as your own.** Registering
> `dacrypt.github.io` (or any other user's domain) would give their
> app authority over your car. Always host YOUR key on YOUR domain.

## 3. Authenticate plain Fleet API

```bash
tesla config auth fleet
```

The wizard will:

1. Ask for **Client ID** + **Client Secret** from step 1.
2. Call Tesla's `partner_accounts` endpoint to register your domain
   (uses the M2M / client_credentials grant).
3. Open your browser for OAuth 2 + PKCE — log in with your Tesla
   account.
4. Copy the redirect URL back into the terminal. Tesla returns a
   user access token + refresh token, both stored in the system
   keyring (`fleet-access-token`, `fleet-refresh-token`).

Verify:

```bash
tesla vehicle list
# should print your VIN
```

Reads work now — but anything that writes will still 403 on firmware
2024.26+. That's what the next steps fix.

## 4. Generate the signing key pair

```bash
tesla config auth fleet-signed
```

What it does (offline — no network beyond step c below):

| Step | Action |
|------|--------|
| a | Verify `tesla-fleet-api` extras are installed (`uv pip install 'tesla-cli[fleet]'` if missing) |
| b | Generate a fresh `prime256v1` EC key pair at `~/.tesla-cli/keys/` (idempotent — never overwrites an existing pair) |
| c | HTTPS GET `https://<your-domain>/.well-known/appspecific/com.tesla.3p.public-key.pem` — **preflight** |
| d | Dry-run signed handshake — will fail until step 7/8 below |
| e | On success, flip `general.backend = "fleet-signed"` |

**Expected outcome the first time**: step (c) fails because the pubkey
isn't published yet. That's fine — step 5 fixes it.

## 5. Publish the fresh public key

```bash
cp ~/.tesla-cli/keys/public-key.pem \
   ~/dev/<your-username>.github.io/.well-known/appspecific/com.tesla.3p.public-key.pem
cd ~/dev/<your-username>.github.io
git add .well-known
git commit -m "publish Tesla VCP public key"
git push
```

GitHub Pages serves the new file within ~60 seconds. Verify:

```bash
curl -sf https://<your-username>.github.io/.well-known/appspecific/com.tesla.3p.public-key.pem \
  | head -1
# expect: -----BEGIN PUBLIC KEY-----
```

## 6. Re-register the partner so Tesla picks up the new pubkey

**This is the step most people miss.** Tesla **caches** your pubkey
at partner registration time. If you:

- Registered your partner earlier with an older pubkey, OR
- Rotated your local key pair (generated a new one) with
  `tesla config auth fleet-signed`

…then Tesla's cache still has the **old** pubkey. Signed commands
sent by your new private key will not verify against Tesla's cached
public key, and the `tesla.com/_ak/<host>` URL will report *"user not
registered"* or similar.

Fix: re-run partner registration, which POSTs to
`/api/1/partner_accounts` and makes Tesla re-fetch your pubkey from
the well-known URL:

```bash
uv run python3 -c "
from tesla_cli.core.auth import tokens
from tesla_cli.core.auth.oauth import register_fleet_partner
from tesla_cli.core.config import load_config
cfg = load_config()
cs = tokens.get_token(tokens.FLEET_CLIENT_SECRET)
result = register_fleet_partner(cfg.fleet.client_id, cs, region='na')
print(result)
"
```

**`tesla config auth fleet-signed` automates this step from v4.9.2+** —
after a successful pubkey preflight it calls `register_fleet_partner()`
so Tesla always sees the freshly-hosted key. The snippet above is only
needed if you bypassed the CLI flow (manual deployment) or your
`fleet.client_secret` isn't in the keyring.

Verify Tesla now has the right pubkey cached:

```bash
uv run python3 -c "
import httpx
from tesla_cli.core.auth import tokens
from tesla_cli.core.auth.oauth import get_client_credentials_token
from tesla_cli.core.config import load_config
cfg = load_config()
cs = tokens.get_token(tokens.FLEET_CLIENT_SECRET)
m2m = get_client_credentials_token(cfg.fleet.client_id, cs)['access_token']
r = httpx.get(
  f'https://fleet-api.prd.na.vn.cloud.tesla.com/api/1/partner_accounts/public_key?domain={cfg.fleet.domain}',
  headers={'Authorization': f'Bearer {m2m}'}, timeout=15,
)
print('Tesla-cached pubkey prefix:', r.json()['response']['public_key'][:32])
"
# Compare with your local pubkey:
uv run python3 -c "
from cryptography.hazmat.primitives import serialization
from pathlib import Path
pub = serialization.load_pem_public_key((Path.home()/'.tesla-cli/keys/public-key.pem').read_bytes())
print('Local pubkey prefix:        ', pub.public_bytes(
  encoding=serialization.Encoding.X962,
  format=serialization.PublicFormat.UncompressedPoint).hex()[:32])
"
```

The two prefixes **must match**.

## 7. Open the Virtual Key Link in Safari on your iPhone

**Safari only** — Chrome on iOS does not support the Tesla deep link.
The iPhone must be signed into the Tesla app with the account that
**owns the vehicle**.

```
https://tesla.com/_ak/<your-username>.github.io
```

Tesla's server:
1. Looks up the partner registered with `<your-username>.github.io`
   (your app from step 1).
2. Fetches the cached pubkey for that partner (step 6 ensured it is
   the new one).
3. Prompts iOS to open the Tesla app with an "Add Key" sheet.

## 8. Tap "Add Key" in the Tesla app

Confirm with Face ID / passcode. The key appears under **Security →
Manage Keys** on the vehicle. No physical proximity required — this
is the Virtual Key flow.

## 9. Flip the CLI backend

```bash
tesla config set backend fleet-signed
```

Every subsequent `tesla vehicle …` / `tesla climate …` / `tesla
charge …` command is now signed end-to-end with
`~/.tesla-cli/keys/private-key.pem`.

## 10. Verify

```bash
tesla doctor
# T2 rows (flash_lights, door_lock, sentry_mode, …) should flip
# from "external-blocker" → "ok"

tesla vehicle flash-lights
# ✓ command sent; lights flash within ~3s
```

If anything still 403s, re-check the fingerprint match from step 6.
99% of the time the Tesla-cached pubkey is stale.

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `tesla.com/_ak/<host>` → *"user not registered"* | Tesla's cached pubkey doesn't match your local key | Re-run step 6 (re-register partner) |
| `tesla.com/_ak/<host>` → *"third-party app not approved"* | Partner account not registered with Tesla | Step 3 (`config auth fleet`) must succeed first |
| Preflight 404 | Pubkey not published at `.well-known/appspecific/` | Step 5, then wait ~60s for GitHub Pages |
| Preflight 200 but handshake still fails | You published the file, but Tesla's cache is stale | Step 6 again — publishing alone is not enough |
| `HTTP 403 Vehicle Command Protocol required` on every command | `backend` still set to `fleet` (not `fleet-signed`) | `tesla config set backend fleet-signed` |
| `NotPaired` after step 8 | Add Key tap not confirmed, or different iCloud account | Re-open `tesla.com/_ak/<host>` in Safari on the Tesla-owner's iPhone |
| Commands hang or `ModuleNotFoundError: tesla_fleet_api` | Optional extra missing | `uv pip install 'tesla-cli[fleet]'` |
| Locked out — want to revert to read-only | Handshake mis-config | `tesla config set backend fleet` (reads keep working) |

## Rotating keys

To generate a fresh key pair (e.g. suspected leak of the private key):

```bash
rm ~/.tesla-cli/keys/{private,public}-key.pem
tesla config auth fleet-signed   # step 4 re-runs, generates a new pair
# Step 5: publish the new public-key.pem to your host repo
# Step 6: re-register partner (MANDATORY — Tesla still has old pubkey)
# Step 7-8: open tesla.com/_ak/<host> and re-tap Add Key — Tesla
#           shows a new fingerprint; confirm. Old key is invalidated
#           automatically.
```

The private key never leaves `~/.tesla-cli/keys/private-key.pem`
(mode `0600`). It is not stored in the system keyring; the file is
the source of truth.

## What is hosted where

| Artifact | Location | Visibility |
|---|---|---|
| Private key | `~/.tesla-cli/keys/private-key.pem` | local, mode `0600` |
| Public key (serving copy) | `<your-host>/.well-known/appspecific/com.tesla.3p.public-key.pem` | public on the internet |
| Public key (working copy) | `~/.tesla-cli/keys/public-key.pem` | local |
| Client ID | `~/.tesla-cli/config.toml` (`fleet.client_id`) | local, not secret |
| Client Secret | system keyring (`fleet-client-secret`) | local, secret |
| Access / Refresh tokens | system keyring (`fleet-access-token`, `fleet-refresh-token`) | local, secret |

**Nothing VCP-related should ever land in this `dacrypt/tesla` repo
or any fork of it.** `.gitignore` blocks `*.pem`, `*.key`, `keys/`,
and `.well-known/` as a belt-and-suspenders safety net.
