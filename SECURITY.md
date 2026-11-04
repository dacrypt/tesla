# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| 4.8.x   | ✅         |
| < 4.8   | ❌         |

## Reporting a Vulnerability

If you discover a security vulnerability in tesla-cli, please report it responsibly:

1. **Do NOT open a public GitHub issue**
2. Email: dacrypt@users.noreply.github.com
3. Include:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact

We will respond within 48 hours and provide a fix timeline.

## Security Practices

- **Credentials**: Prefer the system keyring (macOS Keychain, GNOME Keyring, Windows Credential Locker) or injected environment variables. Notification URLs and configuration exports can contain credentials; keep them private.
- **Tokens**: OAuth2 access/refresh tokens with automatic refresh. No hardcoded secrets.
- **PII**: VINs, reservations, notification destinations and configuration backups may identify a person or vehicle. Never commit or publish them. Use `--anon` when sharing supported command output and review it before publication.
- **Network**: All API calls direct to Tesla (no third-party relay). Self-hosted telemetry.
- **Docker**: Non-root container, health checks, named volumes for persistent data.

## Past incidents

- **October 2026** — a configuration backup (`tesla-config-backup.json`)
  generated inside the project checkout was committed, exposing a Telegram bot
  token (revoked), a VIN, an order reservation and a Fleet API client ID.
  History was rewritten, affected pull requests and cached objects were purged
  by GitHub Support, and contaminated PyPI sdists were deleted. Since 5.4.0
  the CLI refuses to write backups/exports inside a git work tree and writes
  them `0600` under `~/.tesla-cli/backups/`.

## Publication checks

CI scans all reachable history and tracked files using pinned Gitleaks, plus VIN, reservation and Telegram rules. Package publication also scans generated archives. Findings are never uploaded as public reports. GitHub secret scanning and push protection should remain enabled.

Install Gitleaks 8.30.1 and enable the local publication guard:

```sh
git config core.hooksPath .githooks
scripts/secret-scan.sh
```

The hook fails closed when the scanner is unavailable. A local hook can be bypassed; CI and GitHub push protection provide additional checks. Review every allowlist change; only explicitly audited synthetic fixtures may be exempted.

Keep local configuration outside the checkout. `tesla-config.example.json` contains no working credentials or personal identifiers; its empty fields and example domain must be replaced privately.

See [history resynchronization](docs/history-resynchronization.md) after a sensitive-data history rewrite.
