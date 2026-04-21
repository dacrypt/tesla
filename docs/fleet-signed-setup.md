# Vehicle Command Protocol (signed commands) — setup

## What is VCP?

Vehicle Command Protocol (VCP) is Tesla's end-to-end-encrypted command channel.
The CLI signs every outbound command with an elliptic-curve private key that
the car has already accepted; the car rejects anything else.

## Why it's required on 2024.26+

Firmware `2024.26` and later reject unsigned Fleet API commands silently:
the HTTP call succeeds but the car ignores it. To actually control a modern
Tesla through the Fleet API you MUST pair a VCP key with the vehicle and
sign commands with it.

## The `tesla config auth fleet-signed` flow

One command walks you through pairing:

```
tesla config auth fleet-signed
```

It will:

1. Check that the `tesla-fleet-api` Python dependency is installed (run
   `uv pip install 'tesla-cli[fleet]'` if not).
2. Generate a `prime256v1` key pair under `~/.tesla-cli/keys/` — if a pair
   already exists, it is reused verbatim (idempotent; never overwritten).
3. Preflight-check that your public key is reachable at your registered
   fleet domain (see below).
4. Perform a dry-run signed handshake against your default VIN.
5. On success, flip `general.backend = "fleet-signed"` so subsequent
   commands go through the signed channel.

If the preflight or handshake fails, the CLI prints a short remediation
block and exits `1` without changing any config. You can always fall back:

```
tesla config set backend fleet
```

## Publishing your public key

Tesla fetches your app's public key from a fixed well-known URL on your
registered domain:

```
https://<your-fleet-domain>/.well-known/appspecific/com.tesla.3p.public-key.pem
```

Host `public-key.pem` (generated in step 2 above) at that exact path. The
simplest recipe is GitHub Pages:

1. Create a public repo (or reuse one) served at your fleet domain.
2. Commit the public key to
   `.well-known/appspecific/com.tesla.3p.public-key.pem`.
3. Verify from a browser that the file serves as `text/plain` with the
   `-----BEGIN PUBLIC KEY-----` header intact.
4. Re-run `tesla config auth fleet-signed`.

After the car accepts the key pairing under **Manage Keys → Add Key** in
the Tesla app, signed commands will work immediately.
