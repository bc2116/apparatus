# PR-38 shared interface

`apparatus_core.skills` is owned by the lead:

- `BUILTIN_SKILLS`: dict of the five legacy relative procedure paths to prefixed native names.
- `BUILTIN_PATHS`: dict of their exact canonical `.agents/skills/NAME/SKILL.md` paths to names.
- `canonical_path(name) -> str` and `valid_name(value) -> bool`.
- `validate_skill(content: bytes | str, expected_name: str) -> list[str]`: empty means valid common portable format. It adds no action authority.
- `legacy_pointer(legacy_path) -> bytes`: exact procedure-schema compatibility stub. `is_legacy_pointer(legacy_path, content) -> bool` recognizes full LF/CRLF variants only.
- `SKILL_INDEX`: exact complete text block for the canon. `has_skill_index(content: bytes) -> bool` recognizes this whole shipped block, including CRLF. This is bounded evidence of the new set even if its directories disappear; delimiters alone are insufficient.
- `is_shipped_skill_orientation(relative: str, content: bytes) -> bool`: recognizes complete known PR-38 `Welcome.md` or `System/README.md` bytes by explicit digest, normalizing CRLF only. These shipped files are installation evidence even when custom canon has no Skill index and all native directories disappear. Headers, path mentions, edited files and other filenames do not qualify. Preserve these historical digests when adding later shipped versions; this evidence helper grants no write ownership over customized instructions.

Payload author: replace the current procedure index in stock AGENTS.md with the complete SKILL_INDEX block. Do not duplicate workflow bodies in that index. Other orientation files can point to it. Generate five standard files at BUILTIN_PATHS and remove only the retired files from both fresh payloads. Preserve procedure workflow behavior except format/path/vocabulary changes. Source/embedded manifests move to the new paths. No native wrappers or symlinks.

Migration author: use helpers above; do not duplicate pointer rendering. Reuse existing instruction_updates/deployment transactions. Recognize PR-36 shipped instruction bytes before changing payload, and exact stubs thereafter. Preserve valid custom canonical Skills, reject unresolved customized legacy built-ins before any writes. Include every canonical target and existing legacy source in expected byte/absence preimages. Keep unrelated custom canon/Skills untouched. Notify the lead if deployment or overlay semantics need a shared change.

Lead: update overlay paths and validation, check's bounded evidence/partial/mixed diagnostics, declared recovery paths and historical validation. A full recognized Skill index is an exact shipped canon fragment for migration evidence, not ownership of the whole custom canon. Native options remain outside this format cut.

Migration source boundary: an entirely legacy-format custom payload remains supported. Any exact built-in Skill file/directory or the complete shipped Skill index in its canon makes it a native-format source; then all five canonical source files must be present and valid before planning any writes. Empty managed directories or a retained stock index cannot disguise a damaged native payload as a legacy payload. Unrelated native Skill paths alone do not trigger conversion.
A native-format source must not contain any of the five mapped legacy procedure paths, even as stubs; otherwise generic payload copying could publish a second workflow. Existing target legacy files are still migrated as specified, and unrelated custom legacy paths remain outside this source restriction.
