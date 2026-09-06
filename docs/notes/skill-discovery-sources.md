# Native Skill discovery evidence

Retrieved 2026-09-06. Primary documentation establishes these paths; it does not certify an installed app or prove invocation.

## Portable format

A Skill directory contains SKILL.md with YAML name and description, followed by Markdown instructions. Name matches its parent directory: 1-64 lowercase alphanumeric/hyphen characters, no leading/trailing/consecutive hyphens. Description is 1-1024 characters. Optional resources are allowed. Filesystem discovery paths belong to clients, not the standard. Apparatus ordinary-file fallback is its own compatibility contract.

Source: [Agent Skills specification](https://agentskills.io/specification).

## Codex

SKILL.md requires name and description. Codex scans .agents/skills from its current directory through repository root; user skills live under ~/.agents/skills. Named Skill directories can be symlinks. Equal names are not merged and may both appear. Metadata is loaded first; a selected Skill then loads its full instructions. Explicit and description-based invocation are supported. Standalone Skills work in the desktop app, CLI and IDE extension; this is documentation, not an Apparatus runtime test. Parent discovery does not establish discovery across an independent project repository boundary.

Source: [OpenAI Build skills](https://learn.chatgpt.com/docs/build-skills), reached by the official developers.openai.com/codex/skills redirect. The Skills API is not the source for local filesystem discovery.

## Claude Code

Native project files are .claude/skills/NAME/SKILL.md, with personal ~/.claude/skills and enterprise/plugin scopes. Claude accepts optional name/description locally; Apparatus will use both for portability. Named Skill directories may be symlinks, and the same target reached multiple ways loads once. Nested project Skills have directory scope. Equal names across levels follow documented precedence. This does not establish detection of a separate work area's canonical directory from a bound project.

Source: [Claude Code Skills](https://code.claude.com/docs/en/skills).

## Cursor

Project discovery includes .agents/skills and .cursor/skills; personal equivalents exist. Compatibility locations include .claude/skills and .codex/skills. SKILL.md requires name and description, with name matching the parent directory. Skill roots are searched recursively; nested project roots apply to their directory. The reviewed page does not establish symlink handling or duplicate-name behavior when both canonical and compatibility roots expose one Skill. Local discovery is distinct from cloud Skill synchronization.

Source: [Cursor Agent Skills](https://cursor.com/docs/skills).

## Implementation boundary

No native-app runtime probe was performed for this note. Do not infer discovery from an Apparatus validator, Markdown presence, or doc-only evidence. Do not promise invocation. One canonical body and thin owned adapters can preserve portability, but actual discovery, duplicates, cross-repository context and Windows filesystem behavior require focused evidence. Existing third-party and custom Skills stay user-owned.
