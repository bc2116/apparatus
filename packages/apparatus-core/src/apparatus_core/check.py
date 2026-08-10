"""Deterministic workspace checks built on the v0 record schemas."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from apparatus_core import records
from apparatus_core import shims
from apparatus_core.ignore import IgnoreReport, load_ignore_rules
from apparatus_core.render import (
    RenderError,
    is_reparse_path,
    normalize_target,
    rendered_shims,
)


@dataclass(frozen=True)
class Finding:
    """One actionable, machine-readable problem found in a workspace."""

    code: str
    path: str
    hint: str


@dataclass(frozen=True)
class CheckResult:
    """The complete result of checking one workspace."""

    findings: tuple[Finding, ...]
    records_checked: int
    ignore_report: IgnoreReport = field(default_factory=IgnoreReport)

    @property
    def ignored_paths(self) -> int:
        return self.ignore_report.skipped_paths

    @property
    def ok(self) -> bool:
        return not self.findings


REQUIRED_ENTRIES: tuple[tuple[str, bool], ...] = (
    ("Welcome.md", False),
    ("Goals", True),
    ("Decisions", True),
    ("Projects", True),
    ("Library", True),
    ("Deliverables", True),
    ("Memory/People", True),
    ("Memory/Facts", True),
    ("System", True),
)

RECORD_FOLDERS: tuple[tuple[str, str], ...] = (
    ("Goals", "goal"),
    ("Decisions", "decision"),
    ("Memory/People", "person"),
    ("Memory/Facts", "fact"),
    ("System/procedures", "procedure"),
    ("System/receipts", "receipt"),
)


def _relative(path: Path, workspace: Path) -> str:
    return path.relative_to(workspace).as_posix()


def _record_files(folder: Path) -> list[Path]:
    """Return Markdown files below *folder*, omitting every dot-directory."""
    found: list[Path] = []
    for path in folder.rglob("*.md"):
        relative_parts = path.relative_to(folder).parts
        if path.name.startswith(".") or any(
            part.startswith(".") for part in relative_parts[:-1]
        ):
            continue
        if path.is_file():
            found.append(path)
    return sorted(found)


def _declared_kind(data: dict) -> str | None:
    schema_id = data.get("schema")
    prefix = "apparatus/"
    suffix = "@v0"
    if not isinstance(schema_id, str) or not schema_id.startswith(prefix) or not schema_id.endswith(suffix):
        return None
    return schema_id[len(prefix) : -len(suffix)]


def _problem_code(problem: str) -> str:
    if problem.startswith("required field missing or empty:"):
        return "missing-required-field"
    if problem.startswith("unknown record kind:"):
        return "unknown-record-kind"
    if problem.startswith("filename "):
        return "filename-rule-error"
    return "record-schema-error"


def _record_findings(path: Path, workspace: Path, expected_kind: str) -> list[Finding]:
    relative = _relative(path, workspace)
    try:
        data, _body = records.parse_record(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError):
        return [Finding("record-read-error", relative, "Make this record readable as UTF-8 text.")]
    except Exception:
        return [
            Finding(
                "frontmatter-parse-error",
                relative,
                "Start and close YAML frontmatter with --- and use a YAML mapping.",
            )
        ]

    declared_kind = _declared_kind(data)
    if declared_kind is None:
        return [
            Finding(
                "record-schema-error",
                relative,
                f"Set schema to {records.SCHEMAS[expected_kind].schema_id}.",
            )
        ]
    if declared_kind not in records.SCHEMAS:
        return [
            Finding(
                "unknown-record-kind",
                relative,
                "Use one of the seven v0 record kinds in the schema field.",
            )
        ]
    if declared_kind != expected_kind:
        return [
            Finding(
                "kind-folder-mismatch",
                relative,
                f"Move this {declared_kind} record to its matching folder or use {expected_kind}.",
            )
        ]

    return [
        Finding(_problem_code(problem), relative, "Correct this record to match its v0 schema.")
        for problem in records.validate(expected_kind, data, filename=path.name)
    ]


def _profile_findings(path: Path, workspace: Path) -> list[Finding]:
    relative = _relative(path, workspace)
    try:
        data = records.yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError):
        return [Finding("record-read-error", relative, "Make this profile readable as UTF-8 text.")]
    except Exception:
        return [
            Finding("frontmatter-parse-error", relative, "Use a YAML mapping for this profile.")
        ]
    if not isinstance(data, dict):
        return [Finding("record-schema-error", relative, "Use a YAML mapping for this profile.")]
    return [
        Finding(_problem_code(problem), relative, "Correct this profile to match its v0 schema.")
        for problem in records.validate("profile", data, filename=path.name)
    ]


def _machine_report_findings(path: Path, workspace: Path) -> list[Finding]:
    relative = _relative(path, workspace)
    try:
        records.parse_record(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError):
        return [Finding("record-read-error", relative, "Make this machine report readable as UTF-8 text.")]
    except Exception:
        return [
            Finding(
                "frontmatter-parse-error",
                relative,
                "Use parseable YAML frontmatter in this machine report.",
            )
        ]
    return []


def _shim_findings(
    workspace: Path,
    registry: tuple[tuple[str, str], ...] | None,
) -> list[Finding]:
    """Compare every registered shim to its deterministic in-memory render."""
    active_registry = shims.SHIM_REGISTRY if registry is None else registry
    try:
        expected = rendered_shims(workspace, registry=active_registry)
    except RenderError:
        # With no usable canon, an existing target is stale while an absent
        # target remains missing. Do not let one render error blur the two.
        return [
            Finding(
                "shim-drift" if _shim_target_present(workspace, target) else "shim-missing",
                target,
                "Run `apparatus render` after adding AGENTS.md.",
            )
            for target, _template in active_registry
        ]

    findings: list[Finding] = []
    for shim in expected:
        target = workspace / shim.target
        if not _safe_shim_file(workspace, shim.target):
            code = "shim-drift" if _shim_target_present(workspace, shim.target) else "shim-missing"
            findings.append(
                Finding(code, shim.target, "Run `apparatus render` to regenerate this shim.")
            )
            continue
        try:
            actual = target.read_bytes()
        except OSError:
            actual = None
        if actual != shim.content:
            findings.append(
                Finding("shim-drift", shim.target, "Run `apparatus render` to regenerate this shim.")
            )
    return findings


def _safe_shim_file(workspace: Path, target: str) -> bool:
    """Return whether target is a regular workspace file without symlink traversal."""
    try:
        relative = normalize_target(target)
    except RenderError:
        return False
    if is_reparse_path(workspace):
        return False
    current = workspace
    for part in relative.parts:
        current /= part
        if is_reparse_path(current):
            return False
    return current.is_file()


def _shim_target_present(workspace: Path, target: str) -> bool:
    """Detect a target or unsafe symlink component without reading through it."""
    try:
        relative = normalize_target(target)
    except RenderError:
        return False
    if is_reparse_path(workspace):
        return True
    current = workspace
    for part in relative.parts:
        current /= part
        if is_reparse_path(current):
            return True
    return current.exists()


def check_workspace(
    workspace: str | Path,
    *,
    shim_registry: tuple[tuple[str, str], ...] | None = None,
) -> CheckResult:
    """Check a workspace tree and its v0 records without changing it."""
    root = Path(workspace)
    findings: list[Finding] = []
    rules = load_ignore_rules(root)
    findings.extend(
        Finding(
            issue.code,
            "System/ignore",
            (f"Line {issue.line}: " if issue.line else "") + issue.message,
        )
        for issue in rules.issues
    )
    if not rules.valid:
        return CheckResult(tuple(findings), 0, rules.report())
    for relative, is_directory in REQUIRED_ENTRIES:
        path = root / relative
        exists = path.is_dir() if is_directory else path.is_file()
        if not exists:
            findings.append(
                Finding(
                    "tree-missing-entry",
                    relative,
                    "Create the required workspace entry at this path.",
                )
            )

    records_checked = 0
    built_in_ignored = 0
    user_ignored = 0
    for relative, kind in RECORD_FOLDERS:
        folder = root / relative
        if not folder.is_dir():
            continue
        for path in _record_files(folder):
            classification = rules.classification(_relative(path, root))
            if classification is not None:
                if classification == "built-in":
                    built_in_ignored += 1
                else:
                    user_ignored += 1
                continue
            records_checked += 1
            findings.extend(_record_findings(path, root, kind))

    profile = root / "System/profile.yaml"
    if profile.is_file():
        classification = rules.classification(_relative(profile, root))
        if classification is not None:
            if classification == "built-in":
                built_in_ignored += 1
            else:
                user_ignored += 1
        else:
            records_checked += 1
            findings.extend(_profile_findings(profile, root))
    machine_report = root / "System/machine-report.md"
    if machine_report.is_file():
        classification = rules.classification(_relative(machine_report, root))
        if classification is not None:
            if classification == "built-in":
                built_in_ignored += 1
            else:
                user_ignored += 1
        else:
            findings.extend(_machine_report_findings(machine_report, root))

    findings.extend(_shim_findings(root, shim_registry))

    return CheckResult(
        tuple(findings),
        records_checked,
        rules.report(
            built_in_paths=built_in_ignored, user_paths=user_ignored
        ),
    )
