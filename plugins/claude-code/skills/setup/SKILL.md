---
name: setup
description: >
  Set up tesla-cli — install, authenticate with Tesla, discover your VIN,
  and configure your backend. Use for first-time setup or reconfiguration.
disable-model-invocation: true
allowed-tools: Bash(uv *) Bash(tesla *) Bash(which *) Bash(pip *)
---

# Tesla CLI Setup

Guide the user through installing and configuring tesla-cli.

## Step 1: Check Prerequisites

```bash
python3 --version    # Python 3.12+ required
which uv             # uv package manager required
```

If `uv` is not installed:
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

## Step 2: Install tesla-cli

```bash
uv tool install tesla-cli
```

With optional features:
```bash
uv tool install "tesla-cli[serve]"       # + REST API + web dashboard
uv tool install "tesla-cli[teslaMate]"   # + TeslaMate analytics
uv tool install "tesla-cli[fleet]"       # + Tesla Fleet API
uv tool install "tesla-cli[pdf]"         # + PDF dossier export
uv tool install "tesla-cli[serve,teslaMate,fleet,pdf]"  # all features
```

## Step 3: Interactive Setup

```bash
tesla setup
```

The setup wizard handles:
1. **Tesla OAuth2 authentication** — opens browser, user logs in, pastes redirect URL
2. **VIN auto-discovery** — finds your Tesla(s) automatically
3. **Order number detection** — finds active orders if any
4. **Backend selection** — Owner API (free), Tessie ($13/mo), or Fleet API (free)
5. **First data build** — queries all 15 data sources

## Step 4: Verify

```bash
tesla config show                # show config + token status
tesla vehicle list               # confirm vehicle access
tesla charge status --oneline    # quick battery check
```

## Step 5 (Optional): Additional Setup

### Notifications
```bash
tesla notify add tgram://BOT_TOKEN/CHAT_ID   # Telegram
tesla notify add discord://webhook_id/token   # Discord
tesla notify test                              # verify
```

### TeslaMate Analytics
```bash
tesla teslaMate install          # managed Docker stack
# or
tesla teslaMate connect postgresql://user:pass@host:5432/teslamate
```

### Multi-Vehicle
```bash
tesla config alias modely VIN1
tesla config alias model3 VIN2
```

## Response Guidelines

- Check what's already installed/configured before suggesting steps
- Run `which tesla` and `tesla config show --json` first to assess current state
- Skip steps that are already done
- Celebrate when setup is complete — the user is about to control their Tesla from the terminal!
