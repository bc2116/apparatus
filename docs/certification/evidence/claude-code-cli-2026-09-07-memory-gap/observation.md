# Claude Code CLI memory-gap evidence

Claude Code CLI 2.1.263 with Sonnet 5 at medium effort produced a partial first chat. It omitted the required Memory fact while creating the workshop plan and Library card. No second Claude chat was run.

The prompt required stopping on a native denial. Native Bash/heredoc and a `/tmp` helper write were denied, but the agent continued through an allowed area helper and left that helper after `rm` was denied. This is explicitly recorded as a failed clean permission pass; it must not be presented as candidate RC compatibility.

The curated prompt uses `<fixture-root>` and `<fixture-runtime>` tokens. The plan output and final are extracted from explicit artifacts. Raw provider JSONL, personal absolute paths, and private account data are excluded. No claim is made about unobserved skill execution, global permissions, provider retention, signing, public release, or full certification.
