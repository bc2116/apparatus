"""Data-only registry for generated AI-app instruction shims."""

from __future__ import annotations

# Keep this ordered: output and findings follow registry order.  A new shim is
# one template plus one row here; render and check intentionally have no
# per-shim branches.
SHIM_REGISTRY: tuple[tuple[str, str], ...] = (
    ("CLAUDE.md", "claude-md.template"),
    (".cursor/rules/apparatus.mdc", "cursor-rules.template"),
    (".github/copilot-instructions.md", "copilot-instructions.template"),
)
