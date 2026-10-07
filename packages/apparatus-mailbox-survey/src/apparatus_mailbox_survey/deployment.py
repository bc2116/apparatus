"""Explicit, create-only deployment of the released Mailbox Survey Skill."""

from contextlib import ExitStack
from importlib import resources
import os
from pathlib import Path
import stat
from types import SimpleNamespace

from . import __version__

PACKAGE_ID = "apparatus-mailbox-survey"
SKILL_ROOT = ".agents/skills/apparatus-mailbox-survey"
ASSETS = {
    f"{SKILL_ROOT}/SKILL.md": "skills/apparatus-mailbox-survey/SKILL.md",
    f"{SKILL_ROOT}/references/report-format.md": "skills/apparatus-mailbox-survey/references/report-format.md",
}
MAX_ASSET_BYTES = 1024 * 1024
PARTIAL_INSTALL_GUIDANCE = (
    "Installation may be partial. Inspect with status; use repair only when "
    "remaining assets match the package. Review and preserve conflicting edits. "
    "Do not use the Skill until status reports current."
)


class DeploymentError(ValueError):
    """A fixed, content-free explanation and command exit status."""

    def __init__(self, message, code=2):
        super().__init__(message)
        self.code = code


def _core():
    """Load lifecycle-only dependencies; validation never reaches this function."""
    try:
        from apparatus_core.fs_transactions import WorkspaceAnchor, PosixIdentity, PosixOwnedFile, PosixOwnedDirectory
        from apparatus_core.skills import validate_skill
        from apparatus_core.workspace_layout import ManagedLayout, _parse, _root_identity
    except ImportError as error:
        raise DeploymentError(
            "Lifecycle commands require the lifecycle extra with compatible apparatus-core; install it explicitly."
        ) from error
    class LifecycleAnchor(WorkspaceAnchor):
        def read_file(self, relative):
            # Enrollment validation rereads a file whose publication proof
            # remains open. Read-only sharing must coexist with that proof on
            # Windows; the default core reader also requests DELETE access.
            proof = self.capture_file(relative, publication_compatible=True)
            try:
                return proof.content, proof.identity
            finally:
                proof.close()

    anchor_type = LifecycleAnchor
    if os.name == "posix":
        class BoundedAnchor(LifecycleAnchor):
            @staticmethod
            def _write_at(parent, name, content, mode):
                # Exclusive creation can leave partial bytes on failure. Never
                # remove by pathname after a separate identity/content check.
                descriptor = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                                     mode, dir_fd=parent)
                try:
                    view = memoryview(content)
                    written = 0
                    while written < len(view):
                        count = os.write(descriptor, view[written:])
                        if count <= 0:
                            raise OSError("Asset write did not complete")
                        written += count
                    os.fsync(descriptor)
                    status = os.fstat(descriptor)
                    return PosixIdentity(status.st_dev, status.st_ino, status.st_size, status.st_mtime_ns)
                finally:
                    os.close(descriptor)

            def create_file(self, relative, content, mode=0o600, *, owned_parent=None):
                if not self.root_is_current():
                    raise OSError("Workspace root changed")
                parent, name = self._parent(relative)
                try:
                    if not self._parent_is_current(Path(relative), parent):
                        raise OSError("Asset parent changed")
                    if owned_parent is not None:
                        status = os.fstat(parent)
                        if (Path(relative).parent != owned_parent.relative
                                or owned_parent.parent < 0
                                or not self._parent_is_current(owned_parent.relative, owned_parent.parent)
                                or (status.st_dev, status.st_ino) != (owned_parent.device, owned_parent.inode)):
                            raise OSError("Owned asset parent changed")
                    identity = self._write_at(parent, name, content, mode)
                    if (not self._parent_is_current(Path(relative), parent)
                            or not self._matches(parent, name, identity, content)):
                        raise OSError("Asset or parent changed during creation")
                    return PosixOwnedFile(Path(relative), parent, name, identity, content)
                except Exception:
                    # The created object may have moved or acquired an editor.
                    # Preserve all bytes; only release this retained descriptor.
                    os.close(parent)
                    raise

            def create_directory(self, relative):
                if not self.root_is_current():
                    raise OSError("Workspace root changed")
                parent, name = self._parent(relative)
                try:
                    if not self._parent_is_current(Path(relative), parent):
                        raise OSError("Directory parent changed")
                    os.mkdir(name, 0o700, dir_fd=parent)
                    descriptor = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent)
                    try:
                        status = os.fstat(descriptor)
                    finally:
                        os.close(descriptor)
                    if not self._parent_is_current(Path(relative), parent):
                        raise OSError("Directory parent changed during creation")
                    return PosixOwnedDirectory(Path(relative), parent, name, status.st_dev, status.st_ino)
                except Exception:
                    # Missing or detached directories remain for inspection.
                    os.close(parent)
                    raise

            @staticmethod
            def _read_at(parent, name):
                # Core's reads and ownership checks dispatch
                # through this hook. No base anchor or global patch is used.
                descriptor = os.open(name, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW, dir_fd=parent)
                try:
                    before = os.fstat(descriptor)
                    if not stat.S_ISREG(before.st_mode) or before.st_size > MAX_ASSET_BYTES:
                        raise OSError("Asset is unsafe or oversized")
                    chunks = []
                    remaining = MAX_ASSET_BYTES + 1
                    while remaining:
                        chunk = os.read(descriptor, min(65_536, remaining))
                        if not chunk:
                            break
                        chunks.append(chunk)
                        remaining -= len(chunk)
                    after = os.fstat(descriptor)
                    identity = PosixIdentity(after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
                    initial = PosixIdentity(before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
                    content = b"".join(chunks)
                    if identity != initial or len(content) != after.st_size or len(content) > MAX_ASSET_BYTES:
                        raise OSError("Asset changed or exceeded the read limit")
                    return content, identity
                finally:
                    os.close(descriptor)
        anchor_type = BoundedAnchor
    return SimpleNamespace(anchor=anchor_type, child=_anchor_child,
                           validate_skill=validate_skill, layout=ManagedLayout,
                           parse_layout=_parse, root_identity=_root_identity)


def _anchor_child(parent, parent_path, name):
    """Create/select one child, retaining the same reader adapter at handoff."""
    owned = None
    child = None
    handle = None
    try:
        try:
            owned = parent.create_directory(name)
        except FileExistsError:
            pass
        handle = parent.open_directory(name, shares_delete=owned is not None)
        child = type(parent)(parent_path / name,
                             ancestor_shares_delete=parent.child_ancestor_shares_delete(),
                             root_shares_delete=owned is not None)
        if not child.matches_root_handle(handle) or not child.root_is_current() or not parent.root_is_current():
            raise OSError("Child changed during retained handoff")
        if owned is not None:
            current = child._root_identity
            actual = current if os.name == "posix" else (current.volume, current.index)
            expected = ((owned.device, owned.inode) if os.name == "posix"
                        else (owned.identity.volume, owned.identity.index))
            if actual != expected:
                raise OSError("Created directory was substituted before handoff")
        parent.close_directory(handle)
        handle = None
        return child, owned, owned is not None
    except Exception as failure:
        if handle is not None:
            parent.close_directory(handle)
        if child is not None:
            child.close()
        if owned is not None:
            owned.close()
        raise failure


def _sources(core):
    root = resources.files("apparatus_mailbox_survey").joinpath("resources")
    result = {destination: root.joinpath(*source.split("/")).read_bytes()
              for destination, source in ASSETS.items()}
    if any(not content or len(content) > MAX_ASSET_BYTES for content in result.values()):
        raise DeploymentError("Packaged assets are invalid; reinstall the released module package.")
    if core.validate_skill(result[f"{SKILL_ROOT}/SKILL.md"], PACKAGE_ID):
        raise DeploymentError("Packaged Skill is invalid; reinstall the released module package.")
    for content in result.values():
        content.decode("utf-8", errors="strict")
    return result


def _existing_child(core, parent, name):
    """Retain an existing immediate directory without creating anything."""
    handle = parent.open_directory(name)
    child = None
    try:
        child = core.anchor(parent.workspace / name,
                            ancestor_shares_delete=parent.child_ancestor_shares_delete())
        if not child.matches_root_handle(handle) or not parent.root_is_current() or not child.root_is_current():
            raise OSError("Directory changed during handoff")
        return child
    except Exception:
        if child is not None:
            child.close()
        raise
    finally:
        parent.close_directory(handle)


def _capture(parent, name):
    """Reject nonregular, linked and oversized endpoints before reading."""
    if os.name == "posix":
        status = os.stat(name, dir_fd=parent._root, follow_symlinks=False)
    else:
        status = os.lstat(parent.workspace / name)
    if (not stat.S_ISREG(status.st_mode)
            or getattr(status, "st_file_attributes", 0) & 0x400
            or status.st_size > MAX_ASSET_BYTES):
        raise OSError("Asset is unsafe or oversized")
    return parent.capture_file(name, publication_compatible=True)


def _summary(states):
    values = set(states.values())
    aggregate = ("conflict" if "modified" in values else "current" if values == {"current"}
                 else "absent" if values == {"missing"} else "partial")
    return {"package": PACKAGE_ID, "version": __version__, "state": aggregate, "assets": states}


def operate(workarea: str | Path, action: str = "status") -> dict:
    """Inspect or create only exact missing released assets in an enrolled root.

    Existing files are never overwritten or removed. Failed publication leaves
    partial files and directories in place for inspection. This creates
    generic released guidance, independent of task retention or provider access.
    """
    if action not in {"status", "install", "repair"}:
        raise DeploymentError("Choose status, install, or repair with an explicit enrolled work-area root.")
    core = _core()
    parents = {}
    reads = []
    writes = []
    missing_parents = set()
    states = {}
    try:
        sources = _sources(core)
        root_path = Path(os.path.abspath(os.fspath(workarea)))
        with ExitStack() as stack:
            root = stack.enter_context(core.anchor(root_path))
            parents[Path(".")] = root
            if root.entry_exists(".apparatus"):
                raise DeploymentError("Use the explicitly enrolled work-area root, not a bound project.")
            system = _existing_child(core, root, "System")
            parents[Path("System")] = system
            stack.callback(system.close)
            enrollment = _capture(system, "workspace.yaml")
            reads.append((system, enrollment))
            stack.callback(enrollment.close)
            # Require the fixed marker and reuse core's parser/identity/layout
            # validator with this invocation's safe retained root reader.
            layout = core.layout(root_path, core.parse_layout(enrollment.content), enrollment.content,
                                 enrollment.identity, core.root_identity(root))
            layout.validate(root)

            def validate():
                layout.validate(root)
                if root.entry_exists(".apparatus"):
                    raise OSError("Project control appeared during deployment")
                if any(not parent.root_is_current() for parent in parents.values()):
                    raise OSError("Retained parent changed")
                if any(not parent.matches_owned(proof) for parent, proof in reads + writes):
                    raise OSError("Retained asset changed")
                for relative in missing_parents:
                    if relative.parent in parents and parents[relative.parent].entry_exists(relative.name):
                        raise OSError("Missing directory became occupied")
                for destination, state in states.items():
                    relative = Path(destination)
                    if state == "missing" and relative.parent in parents and parents[relative.parent].entry_exists(relative.name):
                        raise OSError("Missing destination became occupied")

            # Read-only preflight of every fixed directory and asset.
            for destination, expected in sources.items():
                relative = Path(destination)
                current = Path(".")
                for component in relative.parts[:-1]:
                    following = current / component
                    if following not in parents and following not in missing_parents:
                        if current in parents:
                            try:
                                child = _existing_child(core, parents[current], component)
                            except FileNotFoundError:
                                missing_parents.add(following)
                            else:
                                parents[following] = child
                                stack.callback(child.close)
                        else:
                            missing_parents.add(following)
                    current = following
                if current not in parents:
                    states[destination] = "missing"
                else:
                    try:
                        proof = _capture(parents[current], relative.name)
                    except FileNotFoundError:
                        states[destination] = "missing"
                    else:
                        reads.append((parents[current], proof))
                        stack.callback(proof.close)
                        states[destination] = "current" if proof.content == expected else "modified"
            validate()
            result = _summary(dict(states))
            if action == "status":
                return result
            if result["state"] == "conflict":
                raise DeploymentError("Module assets are modified or foreign; preserve them and resolve the conflict before repair.", 1)

            try:
                # No creation occurs until the complete preflight above succeeds.
                for relative in sorted(missing_parents, key=lambda value: (len(value.parts), value.as_posix())):
                    validate()
                    parent = parents[relative.parent]
                    child, owned, _ = core.child(parent, parent.workspace, relative.name)
                    parents[relative] = child
                    stack.callback(child.close)
                    if owned is not None:
                        stack.callback(owned.close)
                    else:
                        raise OSError("Missing directory changed during publication")
                    missing_parents.remove(relative)
                    validate()
                for destination, expected in sources.items():
                    if states[destination] == "current":
                        continue
                    validate()
                    relative = Path(destination)
                    parent = parents[relative.parent]
                    proof = parent.create_file(relative.name, expected)
                    writes.append((parent, proof))
                    stack.callback(proof.close)
                    states[destination] = "current"
                    validate()
                validate()
                return _summary(dict(states))
            except Exception as failure:
                # ExitStack releases every retained file/directory proof. Do
                # not remove even unchanged creations: pathname deletion has
                # a substitution window after its last identity check.
                raise DeploymentError(PARTIAL_INSTALL_GUIDANCE) from failure
    except DeploymentError:
        raise
    except Exception as error:
        raise DeploymentError("Work-area enrollment, assets, or directory boundaries are unsafe or unavailable; preserve files and repair the work area.") from error
