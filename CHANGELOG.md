# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-03-29

### Added

- **Order tracking** — `tesla order status/details/watch` via Tesla Owner API (OAuth2 + PKCE)
- **Vehicle control** — charge, climate, security, media, navigation via Fleet API and Tessie
- **Vehicle dossier** — `tesla dossier build/show/vin/ships/history` aggregating Tesla Owner API, NHTSA recalls, VIN decode, and ship tracking
- **RUNT integration** — Colombia vehicle registry queries via Playwright + OCR
- **SIMIT integration** — Colombia traffic fines queries via Playwright
- **Notifications** — Apprise integration supporting 100+ services (Telegram, Slack, Discord, email, ntfy, etc.)
- **JSON mode** — All commands support `-j/--json` for scripting and `jq` pipelines
- **Secure token storage** — System keyring (macOS Keychain / Linux Secret Service / Windows Credential Manager)
- **Multi-vehicle support** — VIN aliases and per-command `--vin` override
- **Change detection** — `tesla order watch` detects and notifies on any order field change
- **Historical snapshots** — Dossier builds accumulate timestamped snapshots
