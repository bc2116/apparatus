# Native discovery sources

Retrieved September 18, 2026 (America/Los_Angeles). These are documentation
claims, separate from the runtime cases in this directory.

- [OpenAI Build skills](https://learn.chatgpt.com/docs/build-skills), reached from
  the official Codex Skills URL: repository discovery searches `.agents/skills`
  between the current directory and repository root. Equal names are not merged
  and can both appear in selectors. This does not establish discovery across
  an independently bound project boundary.
- [Cursor Agent Skills](https://cursor.com/docs/skills): project locations include
  `.agents/skills/` and `.cursor/skills/`. Cursor recursively discovers Skill
  roots and scopes nested project Skills to their directory. The page describes
  name/description-based relevance, but does not resolve duplicate-name
  precedence or discovery across a separate Apparatus work-area binding.

Local documentation was consulted first. The dated September 6 source note
was insufficient for current discovery claims, so the official pages were
refreshed. No app settings or user-level Skills were changed for this refresh.
