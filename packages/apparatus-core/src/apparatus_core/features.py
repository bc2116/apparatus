"""Profile-controlled core feature selections."""

from __future__ import annotations

from pathlib import Path
from typing import Final

import yaml


DEFAULTS: Final = {
    "library_indexing": True,
    "snapshots": True,
    "ignore_rules": True,
}


def enabled(workspace: str | Path, feature: str) -> bool:
    """Return a feature selection, preserving defaults for older profiles."""
    default = DEFAULTS[feature]
    try:
        data = yaml.safe_load(
            (Path(workspace) / "System/profile.yaml").read_text("utf-8")
        )
    except (OSError, UnicodeError, yaml.YAMLError):
        return default
    if not isinstance(data, dict):
        return default
    selections = data.get("features")
    if not isinstance(selections, dict):
        return default
    value = selections.get(feature, default)
    return value if isinstance(value, bool) else default


def off_receipt_fields(feature: str) -> dict[str, str]:
    """Render the durable, plain-language outcome for a disabled feature."""
    return {
        "summary": f"{feature.replace('_', ' ').capitalize()} is off.",
        "body": "Outcome: this feature is off; say the word and I'll enable it.\n",
    }
