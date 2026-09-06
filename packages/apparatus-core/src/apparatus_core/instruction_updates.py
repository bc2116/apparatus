"""Bounded migration of known shipped workspace instructions.

Only known shipped bytes may be automatically replaced. Other instructions
remain user-owned; a conflicting retired gate is an actionable migration error.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from apparatus_core.fs_transactions import WorkspaceAnchor
from apparatus_core.overlays import OverlayPlan, OverlayWrite
from apparatus_core.payload import PayloadError, preflight_workspace_paths
from apparatus_core.render import rendered_shims_from_bytes

# Original instruction bytes from the pre-rework payload. CRLF is normalized
# for recognition only; the exact captured bytes remain the transaction preimage.
LEGACY_INSTRUCTIONS = {
    "AGENTS.md": "ac76eaa824779d800e2d040473f7e3f61882be572276699325e6ba500abe397e",
    "Welcome.md": "f292587862c4ac7141eecfba14693e39686996c62790b855ae6d7f4e4c12a6b4",
    "System/ignore": "e77d6c14718807b208c1c99f74da8c30b3f279673f3211c9b7ae82aec5d06555",
    "System/policy/standard.md": "d23067a78c1b88306583a0d4c3c15f2588618460c4cbedc95d12e371ed4da2ba",
    "System/policy/private.md": "f48899a5fde9e15d359b7d1591e5000ba17dcb75512024c8ff4aa0c2d52125c2",
    "System/procedures/produce-deliverable.md": "123d047185a83185d658cf7712795d5786d37fd4f1ddf2c3322c5e2e5f7cfb20",
    "System/procedures/research-and-summarize.md": "f561be82c4b1f560e7942c5b7f5b392acd0ade620d5b1aed5e3b4d28adcb4d1e",
    "System/procedures/review-against-checklist.md": "3ff26313de01c63a7747e6c23c5979d8fe637aa746558df8bb63c0a46205f096",
    "System/procedures/weekly-review.md": "4613d8c19ad67a1724b14816b57d814881b338d01cfc9a3ee2d7c1b43202df89",
    "System/procedures/welcome.md": "8c976e064246a27a4b762ac53e82aa0280edf1372c4714fd46203b85273e99ea",
    "CLAUDE.md": "1438f32143f9c1211b2443d2b05fb7b87d71c0eeca77931bc1d6e472a1fc2780",
    ".cursor/rules/apparatus.mdc": "acfcb3006efa4016d38b8b697a8af7630b36ce59b2b3037230b68c0ce3dd7d73",
    ".github/copilot-instructions.md": "4bb639c7bfae8bffb2a36923a2079c861e4eb92f87201095a27296a5795a84a0"
}

# The gate-free PR-32 canon and pointers also upgrade to current Memory guidance.
PREVIOUS_INSTRUCTIONS = {
    "AGENTS.md": "4652aba0d9a9ea2067d8695c38f967327fae6a284da7b45571e89ecc9a2dd66e",
    "CLAUDE.md": "8042d4fc3c111faca7fb6770347ee7cbe66f75bc7aa3c1629c96313f838c3754",
    ".cursor/rules/apparatus.mdc": "82a785af868ba285c12ac86b9fe66b3a61c188ecd016dc9c72b55f976fb2ad76",
    ".github/copilot-instructions.md": "36cc574ea3d7dbb49cd79860489a8cb526bf9fdb8d010c5d69cb5dd673df69ae",
}


def _digest(content: bytes) -> str:
    return hashlib.sha256(content.replace(b"\r\n", b"\n")).hexdigest()


def has_retired_gate(content: bytes) -> bool:
    text = " ".join(content.decode("utf-8", errors="replace").lower().split())
    return any(marker in text for marker in (
        "apparatus egress", "[share]", "## egress rules",
        "run the egress check", "keep outbound work as a draft",
        "your assistant drafts; you send", "with a cleaned copy offered",
    ))


def _read_optional(anchor: WorkspaceAnchor, relative: str) -> bytes | None:
    try:
        return anchor.read_file(relative)[0]
    except FileNotFoundError:
        return None


def retired_instruction_paths(workspace: Path) -> tuple[str, ...]:
    if not workspace.is_dir():
        return ()
    with WorkspaceAnchor(preflight_workspace_paths(workspace)) as root:
        return tuple(
            relative for relative in LEGACY_INSTRUCTIONS
            if has_retired_gate(_read_optional(root, relative) or b"")
        )


def instruction_updates(
    workspace: Path, payload: Path, overlay: OverlayPlan,
) -> tuple[OverlayPlan, dict[str, bytes | None]]:
    """Preflight known instructions and return replacements with exact preimages."""
    replacements: dict[str, OverlayWrite] = {item.relative: item for item in overlay.writes}
    expected: dict[str, bytes | None] = dict.fromkeys(LEGACY_INSTRUCTIONS)
    removals = set(overlay.removals)
    with WorkspaceAnchor(payload) as source:
        proposed: dict[str, bytes] = {}
        for relative in LEGACY_INSTRUCTIONS:
            content = _read_optional(source, relative)
            if content is None:
                continue
            proposed[relative] = content
            if has_retired_gate(proposed[relative]):
                raise PayloadError(
                    f"payload instruction {relative!r} contains the retired sharing gate; "
                    "use the updated starter payload"
                )
    if not workspace.exists():
        return overlay, expected
    with WorkspaceAnchor(workspace) as root:
        for relative, digest in LEGACY_INSTRUCTIONS.items():
            current = _read_optional(root, relative)
            expected[relative] = current
            if current is None:
                continue
            desired = proposed.get(relative)
            if current == desired:
                continue
            if _digest(current) in {digest, PREVIOUS_INSTRUCTIONS.get(relative)} and desired is not None:
                if relative not in removals:
                    replacements[relative] = OverlayWrite(relative, desired)
            elif has_retired_gate(current):
                raise PayloadError(
                    f"custom instruction {relative!r} needs migration; preserve your edits, "
                    "reconcile it with the updated starter and remove the old sharing gate, "
                    "then rerun apparatus init"
                )
            else:
                # A reconciled customization remains user-owned, including when
                # an overlay would normally replace or remove this path.
                replacements.pop(relative, None)
                removals.discard(relative)
    def final_content(relative: str) -> bytes | None:
        if relative in replacements:
            return replacements[relative].content
        current = expected.get(relative)
        return proposed.get(relative) if current is None else current

    canon = final_content("AGENTS.md")
    if canon is not None and any(
        final_content(shim.target) != shim.content
        for shim in rendered_shims_from_bytes(canon)
    ):
        raise PayloadError(
            "AI app pointers disagree with the repaired canon; reconcile custom "
            "pointer instructions into the updated AGENTS.md, run apparatus render WORKSPACE, "
            "then rerun apparatus init"
        )
    return OverlayPlan(
        tuple(replacements.values()),
        tuple(relative for relative in overlay.removals if relative in removals),
    ), expected
