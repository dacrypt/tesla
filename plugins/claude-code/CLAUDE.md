# Tesla Claude Plugin — Contributor Context

## What is this?

A Claude Code plugin that wraps [tesla-cli](https://github.com/dacrypt/tesla) for natural language Tesla vehicle management. The plugin is the AI interface layer; the CLI is the execution engine.

## Structure

```
.claude-plugin/plugin.json    # Plugin manifest (name, version, author)
skills/*/SKILL.md             # 9 skills — each a focused capability
bin/tesla-check               # Pre-flight validation script
docs/design.md                # Architecture design document
```

## Key Rules

1. **Zero PII** — never hardcode VINs, order numbers, names, or emails in any skill file
2. **Dynamic context** — use `!`tesla config show --json`` shell injection for runtime data
3. **CLI is the engine** — skills invoke `tesla` commands, never duplicate business logic
4. **Confirm destructive actions** — unlock, trunk, sentry off, remote-start require user OK
5. **Descriptions under 250 chars** — Claude Code truncates longer descriptions

## Adding a Skill

1. Create `skills/<name>/SKILL.md` with YAML frontmatter
2. Use `allowed-tools: Bash(tesla *)` to scope tool access
3. Set `disable-model-invocation: true` for commands with side effects
4. Set `user-invocable: false` for background knowledge skills
5. Keep SKILL.md under 500 lines — move reference material to separate files

## Testing

```bash
claude --plugin-dir .                  # load plugin locally
/tesla:status                          # test a skill
bin/tesla-check                        # run pre-flight validation
```

## Naming Conventions

- Skill names: lowercase + hyphens only (e.g., `battery-health`)
- Directories match skill names
- Plugin namespace: `tesla:` (e.g., `/tesla:status`)
