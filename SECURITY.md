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

- **Credentials**: Stored in system keyring (macOS Keychain, GNOME Keyring, Windows Credential Locker). Never in plain text files.
- **Tokens**: OAuth2 access/refresh tokens with automatic refresh. No hardcoded secrets.
- **PII**: `--anon` flag masks all personal data. Zero PII in plugin skills or config files.
- **Network**: All API calls direct to Tesla (no third-party relay). Self-hosted telemetry.
- **Docker**: Non-root container, health checks, named volumes for persistent data.
