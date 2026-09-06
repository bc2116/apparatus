"""Deterministic workspace checks built on the v0 record schemas."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from apparatus_core import records
from apparatus_core import shims
from apparatus_core.ignore import IgnoreReport, IgnoreRules, load_ignore_rules
from apparatus_core.instruction_updates import retired_instruction_paths
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

MANAGED_REQUIRED_ENTRIES = tuple(
    entry for entry in REQUIRED_ENTRIES if entry[0] not in {"Projects", "Deliverables", "Decisions"}
) + (("Memory/Decisions", True),)

RECORD_FOLDERS: tuple[tuple[str, str], ...] = (
    ("Goals", "goal"),
    ("Decisions", "decision"),
    ("Memory/Decisions", "decision"),
    ("Memory/People", "person"),
    ("Memory/Facts", "fact"),
    ("System/procedures", "procedure"),
    ("System/receipts", "receipt"),
)


def _relative(path: Path, workspace: Path) -> str:
    return path.relative_to(workspace).as_posix()


def _record_files(
    folder: Path, workspace: Path, rules: IgnoreRules
) -> tuple[list[Path], int, int]:
    """Return visible records and count ignored traversal boundaries once."""
    found: list[Path] = []
    built_in_ignored = 0
    user_ignored = 0

    def count(classification: str) -> None:
        nonlocal built_in_ignored, user_ignored
        if classification == "built-in":
            built_in_ignored += 1
        else:
            user_ignored += 1

    def visit(directory: Path, *, classify_directory: bool = True) -> None:
        if classify_directory:
            classification = rules.classification(
                _relative(directory, workspace), is_directory=True
            )
            if classification is not None:
                count(classification)
                return
        for path in sorted(directory.iterdir(), key=lambda item: item.as_posix()):
            if path.name.startswith(".") or is_reparse_path(path):
                continue
            if path.is_dir():
                visit(path)
                continue
            if path.suffix != ".md" or not path.is_file():
                continue
            classification = rules.classification(_relative(path, workspace))
            if classification is not None:
                count(classification)
            else:
                found.append(path)

    visit(folder)
    return sorted(found), built_in_ignored, user_ignored


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


def _record_repair_hint(kind: str, problem: str) -> str:
    """Describe trusted schema rules without echoing rejected record values."""
    schema = records.SCHEMAS[kind]
    for field in schema.required:
        if problem == f"required field missing or empty: {field}":
            return f"Add a nonempty {field} field to this {kind} record."
    for field, choices in schema.enums.items():
        if problem.startswith(f"{field} must be one of "):
            return f"Set {field} to one of: {', '.join(sorted(choices))}."
    if problem.startswith("schema must be "):
        return f"Set schema to {schema.schema_id}."
    if problem.startswith("labels "):
        return "Set labels to a flat list of text labels."
    if problem.startswith("filename "):
        return (f"Use the {kind} filename rule: {schema.filename_rule}."
                + (" Keep the receipt event consistent with its filename." if kind == "receipt" else ""))
    return f"Ask the assistant to repair this {schema.schema_id} record using its required fields and value types."


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
        Finding(_problem_code(problem), relative, _record_repair_hint(expected_kind, problem))
        for problem in records.validate(expected_kind, data, filename=path.name, body=_body)
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
        Finding(
            _problem_code(problem),
            relative,
            f"Correct this profile field: {problem}",
        )
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


def _learned_skill_findings(workspace: Path, rules: IgnoreRules) -> tuple[list[Finding], int]:
    from apparatus_core import learned_skills
    from apparatus_core.fs_transactions import WorkspaceAnchor
    from apparatus_core.payload import preflight_workspace_paths
    try:
        with WorkspaceAnchor(preflight_workspace_paths(workspace)) as anchor:
            files = learned_skills.registered_files(anchor, excluded=rules.matches)
            return [], len(files)
    except (OSError, ValueError) as error:
        message = str(error) if isinstance(error, learned_skills.LearnedSkillError) else (
            "Adopted Skill ownership or its body is missing or unsafe.")
        message += (" Inspect the registered ownership record and `.agents/skills/learned-NAME/SKILL.md`; "
                    "use `apparatus restore WORKSPACE --list` to look for a known valid pair. "
                    "Preserve custom files and do not silently adopt replacements.")
        return [Finding("learned-skill-check-incomplete", learned_skills.ADOPTED, message)], 0


def _skill_findings(workspace: Path, rules: IgnoreRules) -> tuple[list[Finding], int, int, int]:
    """Read only visible built-in bodies and exact orientation/legacy evidence.

    Directory metadata remains evidence even when bodies are ignored. This
    helper neither lists native directories nor reads third-party Skill files;
    it does not change the older check paths' independent ignore behavior.
    """
    from apparatus_core.fs_transactions import WorkspaceAnchor
    from apparatus_core.payload import PayloadError, preflight_workspace_paths
    from apparatus_core.skills import (
        BUILTIN_PATHS, NEW_SKILL_PATHS, LEGACY_PROCEDURES, has_skill_index, is_legacy_pointer,
        is_shipped_skill_orientation, validate_skill,
    )

    findings: list[Finding] = []
    checked = 0
    skipped: dict[str, str] = {}
    directories: dict[str, bool | None] = {}
    legacy: dict[str, bytes] = {}
    installed = False
    repair = "Preserve custom instructions, then run `apparatus init WORKSPACE` to repair or migrate built-in Skills."

    def incomplete(relative: str) -> None:
        findings.append(Finding("skill-check-incomplete", relative,
                                "Ignore rules hide workflow installation evidence or validation; adjust the rule before checking Skills. " + repair))

    try:
        with WorkspaceAnchor(preflight_workspace_paths(workspace)) as anchor:
            # Directory presence is bounded metadata, even when its body is
            # ignored. Ignoring content cannot turn a partial install into legacy.
            for relative in BUILTIN_PATHS:
                try:
                    directories[relative] = anchor.directory_exists(Path(relative).parent)
                    installed |= bool(directories[relative])
                except OSError:
                    directories[relative] = None
                    installed = True
                    findings.append(Finding("skill-path-unsafe", relative,
                                            "Keep the built-in Skill in regular work-area directories. " + repair))

            for relative in ("AGENTS.md", "Welcome.md", "System/README.md", *LEGACY_PROCEDURES):
                if rules.matches(relative):
                    # Absence and hidden installation evidence are different.
                    try:
                        if not anchor.entry_exists(relative):
                            continue
                    except FileNotFoundError:
                        continue
                    except OSError:
                        findings.append(Finding("skill-evidence-unreadable", relative,
                                                "Make this workflow evidence safe to inspect. " + repair))
                        continue
                    incomplete(relative)
                    continue
                try:
                    content, _ = anchor.read_file(relative)
                except FileNotFoundError:
                    continue
                except OSError:
                    findings.append(Finding("skill-evidence-unreadable", relative,
                                            "Make this workflow evidence a readable regular file. " + repair))
                    continue
                if relative in LEGACY_PROCEDURES:
                    legacy[relative] = content
                    installed |= is_legacy_pointer(relative, content)
                else:
                    installed |= has_skill_index(content) or is_shipped_skill_orientation(relative, content)

            if installed:
                for relative, name in BUILTIN_PATHS.items():
                    if directories[relative] is None:
                        continue
                    try:
                        if not directories[relative] or not anchor.entry_exists(relative):
                            findings.append(Finding("skill-missing", relative,
                                                    ("Upgrade the built-in Skill set. " if relative in NEW_SKILL_PATHS else "") + repair))
                            continue
                        if not _safe_shim_file(anchor.workspace, relative):
                            raise OSError("unsafe Skill endpoint")
                        classification = rules.classification(relative)
                        if classification is not None:
                            skipped[relative] = classification
                            incomplete(relative)
                            continue
                        content, _ = anchor.read_file(relative)
                        checked += 1
                        for problem in validate_skill(content, name):
                            findings.append(Finding("skill-invalid", relative, problem + " " + repair))
                    except OSError:
                        findings.append(Finding("skill-path-unsafe", relative,
                                                "Make this Skill a readable regular file without symbolic links. " + repair))
                for relative, content in legacy.items():
                    if not is_legacy_pointer(relative, content):
                        findings.append(Finding("skill-mixed-state", relative,
                                                "A legacy workflow file remains beside the native Skill set. " + repair))
            if not anchor.root_is_current():
                raise OSError("work area changed during Skill checks")
    except (OSError, PayloadError):
        findings.append(Finding("skill-check-incomplete", ".",
                                "The work-area identity changed or could not be retained; retry the check."))
    return findings, checked, sum(value == "built-in" for value in skipped.values()), sum(value == "user" for value in skipped.values())


def _library_card_findings(workspace: Path, rules: IgnoreRules) -> tuple[list[Finding], int]:
    from apparatus_core.library import cards
    from apparatus_core.fs_transactions import WorkspaceAnchor
    from apparatus_core.payload import preflight_workspace_paths
    try:
        with WorkspaceAnchor(preflight_workspace_paths(workspace)) as anchor:
            files = cards.card_files(anchor, excluded=rules.matches)
        findings = []
        for relative, content in files.items():
            data = cards.parse_card(content, relative)
            # Record parsing supplies the source; source/cache reads still honor
            # original-path ignores. Never include summary text in diagnostics.
            result = cards.read_card(workspace, data["source"], include_text=False)
            if result["card_status"] != "current":
                findings.append(Finding("library-card-" + result["card_status"], relative,
                                        "This card is not current. Check its source and extraction, then ask for a grounded card refresh."))
        return findings, len(files)
    except (OSError, ValueError):
        return [Finding("library-card-check-incomplete", cards.ROOT,
                        "Repair invalid, unsafe or ignored card records before relying on card coverage.")], 0


def _library_source_findings(workspace: Path, rules: IgnoreRules) -> tuple[list[Finding], int]:
    from apparatus_core.library.sources import REGISTRATION_ROOT, list_sources
    try:
        statuses = list_sources(workspace, rules=rules)
    except (OSError, ValueError):
        return [Finding("library-catalog-invalid", REGISTRATION_ROOT,
                        "Repair the Library source records, then run `apparatus library list WORKSPACE`.")], 0
    findings = [Finding("library-source-" + item.status, item.source_path,
                        {"ignored": "This original is intentionally excluded. Review its ignore rule only if you want it included.",
                         "missing": "Restore the original, or use `apparatus library add WORKSPACE PATH` for its new location and remove the old registration.",
                         "unsafe": "Make the original a regular file within its selected project without links; preserve the registration while checking the path.",
                         "unavailable": "Make the selected original readable, then run `apparatus library list WORKSPACE`."}.get(item.status, "Inspect this registration with `apparatus library list WORKSPACE`; preserve the original."))
                for item in statuses if item.status != "available"]
    return findings, len(statuses)


def check_workspace(
    workspace: str | Path,
    *,
    shim_registry: tuple[tuple[str, str], ...] | None = None,
) -> CheckResult:
    """Check a workspace tree and its v0 records without changing it."""
    root = Path(workspace)
    from apparatus_core.project_binding import BindingError, read_project_binding
    from apparatus_core.payload import PayloadError, preflight_workspace_paths
    from apparatus_core.workspace_layout import LayoutError, read_layout
    try:
        if read_project_binding(root) is not None:
            raise BindingError("Use apparatus check PROJECT to check a bound project.")
        # Use the same canonical external ancestors for every check. The final
        # workspace component and paths inside it remain no-follow boundaries.
        root = preflight_workspace_paths(root)
    except (BindingError, PayloadError, OSError) as error:
        return CheckResult((Finding("project-binding-invalid", ".apparatus/workspace.yaml", str(error)),), 0)
    try:
        layout = read_layout(root)
    except LayoutError as error:
        return CheckResult((Finding("workspace-layout-invalid", "System/workspace.yaml", str(error)),), 0)
    findings: list[Finding] = []
    rules = load_ignore_rules(root, respect_feature=False)
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
    for relative, is_directory in (MANAGED_REQUIRED_ENTRIES if layout is not None else REQUIRED_ENTRIES):
        path = root / relative
        exists = path.is_dir() if is_directory else path.is_file()
        if not exists:
            findings.append(
                Finding(
                    "tree-missing-entry",
                    relative,
                    ("Run `apparatus init WORKSPACE` to repair shipped content; preserve any custom-file conflict."
                     if relative == "System" or relative.startswith("System/") or relative in {"AGENTS.md", "CLAUDE.md", "Welcome.md"}
                     else "Restore or create this required directory. Restore lost user records from their original or a known saved point."),
                )
            )

    records_checked = 0
    library_findings, library_count = _library_source_findings(root, rules)
    findings.extend(library_findings)
    records_checked += library_count
    card_findings, card_count = _library_card_findings(root, rules)
    findings.extend(card_findings)
    records_checked += card_count
    built_in_ignored = 0
    user_ignored = 0
    skill_findings, skill_count, skill_built_in, skill_user = _skill_findings(root, rules)
    findings.extend(skill_findings)
    learned_findings, learned_count = _learned_skill_findings(root, rules)
    findings.extend(learned_findings)
    records_checked += skill_count + learned_count
    built_in_ignored += skill_built_in
    user_ignored += skill_user
    for relative, kind in RECORD_FOLDERS:
        folder = root / relative
        if not folder.is_dir():
            continue
        paths, folder_built_in, folder_user = _record_files(
            folder, root, rules
        )
        built_in_ignored += folder_built_in
        user_ignored += folder_user
        for path in paths:
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
    try:
        findings.extend(
            Finding(
                "retired-sharing-instructions", relative,
                "Run `apparatus init WORKSPACE` with the updated package; "
                "reconcile any custom instruction conflicts without discarding your edits.",
            )
            for relative in retired_instruction_paths(root)
        )
    except (OSError, ValueError):
        findings.append(Finding(
            "instruction-read-error", ".",
            "Make workspace instructions readable regular files before retrying the check.",
        ))

    return CheckResult(
        tuple(findings),
        records_checked,
        rules.report(
            built_in_paths=built_in_ignored, user_paths=user_ignored
        ),
    )
