# Vehicle Command Protocol (signed commands) — setup

## What is VCP?

Vehicle Command Protocol (VCP) is Tesla's end-to-end-encrypted command
channel. The CLI signs every outbound command with an elliptic-curve
private key that the car has already accepted; the car rejects anything
else.

## Why it's required on 2024.26+

Firmware `2024.26` and later reject unsigned Fleet API commands with
`HTTP 403 "Tesla Vehicle Command Protocol required"`. To actually
**control** a modern Tesla through the Fleet API you MUST:

1. Pair a VCP key pair with your Tesla Developer app.
2. Host that app's **public** key at a domain you control.
3. Get the vehicle owner (you) to approve the key inside the Tesla app
   on the phone.

After that, every command signed with the matching private key flows
through `/api/1/vehicles/{vin}/signed_command` and executes on the car.

---

## One-time setup overview

```
┌──────────────────────────┐     ┌──────────────────────────┐
│ 1. developer.tesla.com    │──▶─▶│ 2. Allowed Domain:       │
│    create Fleet API app   │     │    https://your-host     │
└──────────────────────────┘     └──────────────────────────┘
                                              │
                                              ▼
┌──────────────────────────┐     ┌──────────────────────────┐
│ 4. tesla.com/_ak/host     │◀────│ 3. publish public key at │
│    Add Key in Tesla app   │     │    /.well-known/...      │
└──────────────────────────┘     └──────────────────────────┘
                  │
                  ▼
         signed commands work ✅
```

`tesla config auth fleet-signed` walks you through steps 2-4 except
publishing the public key — that's the one piece **you must do
yourself** because it requires hosting a file at a URL you control.

---

## ⚠ OSS users: never reuse another person's domain

The domain you register is how Tesla looks up your app. If you paste
someone else's URL into `https://tesla.com/_ak/…` you are giving that
person's app (and therefore their private key) authority over **your
car**. Always publish **your own** public key at **your own** domain.

Concretely: `https://tesla.com/_ak/dacrypt.github.io` binds the car to
the dacrypt app. Don't use it unless you are dacrypt. Pick one of the
options below and register a domain you control.

---

## Choosing how to host your public key

Tesla fetches the public key from a fixed path on whatever domain you
register:

```
https://<your-host>/.well-known/appspecific/com.tesla.3p.public-key.pem
```

You need a publicly-reachable HTTPS URL that returns the file as
`text/plain` (or `application/x-pem-file`) with the `-----BEGIN PUBLIC
KEY-----` header intact. Three common setups:

### Option 1 — GitHub Pages (recommended; free, 5 min)

Every GitHub user already has a free site at `<username>.github.io`.

```bash
# From any empty directory:
gh repo create <username>.github.io --public --clone
cd <username>.github.io
mkdir -p .well-known/appspecific
cp ~/.tesla-cli/keys/public-key.pem .well-known/appspecific/com.tesla.3p.public-key.pem
git add .well-known
git commit -m "publish Tesla VCP public key"
git push

# Enable Pages (if not already):
gh repo edit --enable-pages
```

Register `<username>.github.io` as the Allowed Origin in
developer.tesla.com. The raw-file URL will serve within ~60 seconds.

### Option 2 — Custom domain (if you already own one)

Any HTTPS host works: Apache, Nginx, Caddy, an S3 static bucket, etc.
Drop the key at the well-known path with a valid TLS cert and
register the domain (e.g. `tesla.mydomain.com`) in developer.tesla.com.

### Option 3 — Netlify / Vercel / Cloudflare Pages

The same `.well-known/appspecific/com.tesla.3p.public-key.pem` layout
deployed to any of the free static-hosting providers works. Register
the provider-assigned domain (e.g.
`my-tesla-keys.netlify.app`) in developer.tesla.com.

---

## The `tesla config auth fleet-signed` flow

Once your public key is reachable, run:

```
tesla config auth fleet-signed
```

The command:

1. Verifies the `tesla-fleet-api` Python dependency is installed
   (`uv pip install 'tesla-cli[fleet]'` if not).
2. Generates an idempotent `prime256v1` key pair under
   `~/.tesla-cli/keys/`. If a pair already exists, it is reused
   verbatim — never overwritten.
3. **Prompts for your fleet domain** the first time. You can also
   preset it with `tesla config set fleet-domain <your-host>`.
4. Preflight-fetches
   `https://<your-host>/.well-known/appspecific/com.tesla.3p.public-key.pem`
   — fails fast if it is unreachable or missing the PEM header.
5. Dry-runs a signed handshake against your default VIN. If the
   vehicle has not yet approved the key, the handshake raises
   `NotPaired`; the CLI maps that to the "pair in Tesla app" hint.
6. On success, flips `general.backend = "fleet-signed"` so subsequent
   commands go through the signed channel.

If anything fails, the CLI prints a verbatim rollback hint:

```
To return to read-only Fleet API: tesla config set backend fleet
```

## Pairing the key with your vehicle (one time, per user)

After `auth fleet-signed` preflight passes, Tesla still needs the
**car owner** to confirm the pairing from inside the Tesla app. Open
the following URL on the same iPhone/Android that has the Tesla app
logged in:

```
https://tesla.com/_ak/<your-host>
```

Tap **Add Key** → confirm with Face ID / fingerprint → the key is now
under "Manage Keys" on the vehicle. Signed commands work immediately.

### Alternative: pair via BLE (physical proximity)

If you prefer the Bluetooth pairing flow (no phone app needed):

```
brew install tesla/vehicle-command/tesla-control
tesla-control \
  -key-file ~/.tesla-cli/keys/private-key.pem \
  -vin <your-vin> \
  add-key-request
```

This needs BLE range to the vehicle. The Virtual Key Link URL above
does not.

---

## Verifying end-to-end

```bash
# Check your feature health (should flip T2 rows to "ok"):
tesla doctor

# Try a no-op signed command:
tesla vehicle flash-lights
```

If `tesla doctor` still shows T2 rows as `external-blocker`, your
backend is not yet `fleet-signed` (use
`tesla config set backend fleet-signed`). If flash-lights returns
`403 Vehicle Command Protocol required`, the pairing step is
incomplete — revisit "Pairing the key with your vehicle" above.

## Rotating keys

The CLI is idempotent by design: `auth fleet-signed` will reuse any
existing `~/.tesla-cli/keys/private-key.pem` rather than overwrite it.
To force-rotate, delete the key files and rerun:

```bash
rm ~/.tesla-cli/keys/{private,public}-key.pem
tesla config auth fleet-signed
```

Then re-publish the new public key, re-hit `https://tesla.com/_ak/<your-host>`,
and re-approve in the Tesla app. The old key is invalidated
automatically; no action needed on the vehicle side beyond the new
"Add Key" tap.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Preflight fails (`Public key not found`) | Pubkey not hosted, or host returns 404 | Verify `curl -I https://<host>/.well-known/appspecific/com.tesla.3p.public-key.pem` returns 200 |
| Preflight returns 200 but handshake fails | Pubkey published but never approved in Tesla app | Open `https://tesla.com/_ak/<host>` on your phone, tap Add Key |
| `403 Vehicle Command Protocol required` after pairing | Backend still set to `fleet`, not `fleet-signed` | `tesla config set backend fleet-signed` |
| All commands hang | `tesla-fleet-api` extras not installed | `uv pip install 'tesla-cli[fleet]'` |
| Locked out — want to roll back | Handshake mis-config | `tesla config set backend fleet` (reads still work) |
