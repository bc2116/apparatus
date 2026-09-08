# Codex CLI PR50 Memory continuity evidence

This bounded set compares two actual Codex CLI 0.153.4 runs requested as `gpt-5.6-terra` at medium effort, using an isolated vendor binary, default cache, disabled plugins, workspace write access, and no approval prompts.

The casual first chat completed the plan and Library work but still failed the required Memory fact. The explicit first chat added the clarification to save a sourced Memory fact and verify its record; that first chat saved and verified the fact, then completed the plan and Library card. Its fresh no-save second chat recalled the fact and Library evidence, wrote only the requested facilitator note plus task metadata, and the independent before/after oracle found all pre-existing files unchanged.

The exact prompt difference is preserved in the three normalized prompt files. This payload demonstrates that the explicit instruction produced the required Memory and second-chat outcomes; it does not show that general guidance alone fixed the casual wording. Model identity is recorded as a request from the run setup, not a provider-side assertion beyond available telemetry.

The event stream explicitly records the canonical produce-deliverable skill read and the semantic/persisted outcomes summarized here. Raw provider traces are excluded. The grant for the `~/.apparatus` parent was wider than the selected cache; a bounded probe searched the cache parent, and this evidence makes no OS-level read-confinement claim.
