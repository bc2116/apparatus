"""Deterministic, value-bounded display for structurally valid survey reports."""

import unicodedata

MAX_DISPLAY_CHARS = 240
MAX_DISPLAY_CATEGORIES = 20
MAX_DISPLAY_GAPS = 20
_FORMAT_DIRECTIONS = {
    "LRE", "RLE", "LRO", "RLO", "PDF", "LRI", "RLI", "FSI", "PDI",
}


def _safe_display(value: str) -> str:
    """Escape terminal-unsafe characters after bounding the original string."""
    shortened = value[:MAX_DISPLAY_CHARS]
    escaped = []
    for character in shortened:
        category = unicodedata.category(character)
        direction = unicodedata.bidirectional(character)
        if category.startswith("C") or category in {"Zl", "Zp"} or direction in _FORMAT_DIRECTIONS:
            number = ord(character)
            escaped.append(f"\\u{number:04X}" if number <= 0xFFFF else f"\\U{number:08X}")
        else:
            escaped.append(character)
    result = "".join(escaped)
    if len(value) > MAX_DISPLAY_CHARS:
        result += "… [truncated]"
    return result


def summarize_report(report: dict) -> str:
    """Render only bounded summary fields from a report already validated."""
    scope = report["scope"]
    inventory = report["inventory"]
    total = "unknown" if inventory["total"] is None else str(inventory["total"])
    lines = [
        "Mailbox Survey summary",
        f"Source: {_safe_display(scope['source'])}",
        f"Scope: {_safe_display(scope['description'])}",
        f"Coverage claim: {_safe_display(scope['coverage'])}",
        (
            f"Inventory: total {total}; reviewed {inventory['reviewed']}; "
            f"unavailable {inventory['unavailable']}; skipped {inventory['skipped']}; "
            f"unassessed {inventory['unassessed']}"
        ),
        "Categories (reviewed examples; categories can overlap):",
    ]

    categories = report["categories"]
    if categories:
        for category in categories[:MAX_DISPLAY_CATEGORIES]:
            lines.append(f"- {_safe_display(category['name'])}: {len(category['examples'])}")
        omitted = len(categories) - MAX_DISPLAY_CATEGORIES
        if omitted > 0:
            noun = "category" if omitted == 1 else "categories"
            lines.append(f"- {omitted} additional {noun} omitted.")
    else:
        lines.append("- None reported.")
    lines.append(f"Uncategorized reviewed items: {len(report['uncategorized'])}")

    gaps = report["coverage_gaps"]
    lines.append("Coverage gaps:")
    if gaps:
        for gap in gaps[:MAX_DISPLAY_GAPS]:
            lines.append(f"- {_safe_display(gap)}")
        omitted = len(gaps) - MAX_DISPLAY_GAPS
        if omitted > 0:
            noun = "gap" if omitted == 1 else "gaps"
            lines.append(f"- {omitted} additional coverage {noun} omitted.")
    else:
        lines.append("- None reported.")
    lines.append(
        "This summary reflects report claims; it does not verify evidence, "
        "authority, or actual mailbox coverage."
    )
    return "\n".join(lines)
