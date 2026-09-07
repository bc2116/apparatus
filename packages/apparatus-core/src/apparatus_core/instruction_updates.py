"""Bounded migration of known shipped workspace instructions.

Only known shipped bytes may be automatically replaced. Other instructions
remain user-owned; a conflicting retired gate is an actionable migration error.
"""

from __future__ import annotations

import hashlib
from contextlib import nullcontext
from pathlib import Path

from apparatus_core.fs_transactions import WorkspaceAnchor
from apparatus_core.overlays import OverlayPlan, OverlayWrite
from apparatus_core.payload import PayloadError, preflight_workspace_paths
from apparatus_core.render import owns_shim, rendered_shims_from_bytes
from apparatus_core.skills import (
    BUILTIN_PATHS, LEGACY_PROCEDURES, canonical_path, is_legacy_pointer,
    legacy_pointer, validate_skill, read_skill_payload,
)

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


# PR-33 instructions before task controls; exact-byte migration only.
RETENTION_PREVIOUS_INSTRUCTIONS = {
    "AGENTS.md": "d495acd9a91348aa605a10cc1fc15227ba35ce9165afc449f665e61f82c76f5c",
    "Welcome.md": "dee784338e78b60c696d16e0d99ab736ac9df187375ad4201c8eb3aaff586197",
    "System/ignore": "464121144931e07323d94f4e3bf3ab844b277c47eb74184d5aacf4995f7f5a35",
    "System/policy/standard.md": "67598b46849d097a68f845118c73704854c9a1770c72a8673a246db0fefe4956",
    "System/policy/private.md": "f3e31494bb62a825396369ec7fb4d5c4fd1a250a487b5b6511a003b19703a501",
    "System/procedures/produce-deliverable.md": "16411ec4dc978884e86f59d0f9725c4487e653c169f876284ebdbf125fdc62b0",
    "System/procedures/research-and-summarize.md": "e088f5b5739602d4be7ed93d1a33779e3cc455c78044f8f8e66403f5c8808b11",
    "System/procedures/review-against-checklist.md": "0c8e5d902855b87c125f5fcd85eae6bdbbd5a64e4e7843616a763d52f44d96d3",
    "System/procedures/weekly-review.md": "03d807292d4c28b5561717c35856b80fb70dd9a9ba88709c6990a783a22a379e",
    "System/procedures/welcome.md": "6e0a2285cdb7558a5ad8dc80b44f0c7dd5740a97fcff133b442a88fb82956281",
    "CLAUDE.md": "52089761e522375fdfd7b97cf429b2b0e1ff108b21253e6ef862ef40857a05c9",
    ".cursor/rules/apparatus.mdc": "0caffa63077b3e3fb07516a888fbc94668097e6ebbebe8b2b24f555763cc5423",
    ".github/copilot-instructions.md": "78e02fd2087983da9b56aaa317ea2c105ec902beadab18bd96dbdbf9b7737b56"
}


# PR-34 shipped instructions before work-area enrollment. Exact bytes only.
LAYOUT_PREVIOUS_INSTRUCTIONS = {'AGENTS.md': '7fb4a3f94806cd7e83d1eb0598dee5b7f6254ee8c73915bdf03a78499ab8a803',
 'Welcome.md': 'c4a498b8ac0b0ef89fee6db6d733f30d594cec43886952fdd7540e29c2a58806',
 'System/ignore': '464121144931e07323d94f4e3bf3ab844b277c47eb74184d5aacf4995f7f5a35',
 'System/policy/standard.md': '41e7804882adb2ad4544634028841fcedd2422394ee6d44071654b64621b4613',
 'System/policy/private.md': 'f3472ceaacef9b1dd1091ed56aa56c9aad3b79b2109e79199223e13a84dd2576',
 'System/procedures/produce-deliverable.md': '16411ec4dc978884e86f59d0f9725c4487e653c169f876284ebdbf125fdc62b0',
 'System/procedures/research-and-summarize.md': 'e088f5b5739602d4be7ed93d1a33779e3cc455c78044f8f8e66403f5c8808b11',
 'System/procedures/review-against-checklist.md': '0c8e5d902855b87c125f5fcd85eae6bdbbd5a64e4e7843616a763d52f44d96d3',
 'System/procedures/weekly-review.md': '03d807292d4c28b5561717c35856b80fb70dd9a9ba88709c6990a783a22a379e',
 'System/procedures/welcome.md': 'c23c8e9427030c4196c699df9597e62c242d80d7e73a32cd6ebe7bb596cd7d5b',
 'CLAUDE.md': 'e43e2f2f7fb4d57cedc62205969980bc29445a8f52c0258b708748770f20e5e3',
 '.cursor/rules/apparatus.mdc': '323ce1afdf9cb7bec38105143a7d44a322c3375b8857d4d92c94abd1b7eaee91',
 '.github/copilot-instructions.md': 'd387e08d1c847a5242f8fdc75756cd433343920361d2b19375f6dc2f6e269b44'}


# PR-36 stock work-area instructions before portable Skills. Exact LF/CRLF bytes only.
SKILLS_PREVIOUS_INSTRUCTIONS = {'AGENTS.md': '9182c04aa101e3180004fe0aeac3751b00bde60f909ae596269bdf88400c9b4d',
 'Welcome.md': '9ad4a11406a156894fb501fd9e1c9452d8abd21618c70daa7efea140ab6326f0',
 'System/ignore': '464121144931e07323d94f4e3bf3ab844b277c47eb74184d5aacf4995f7f5a35',
 'System/policy/standard.md': '41e7804882adb2ad4544634028841fcedd2422394ee6d44071654b64621b4613',
 'System/policy/private.md': 'f3472ceaacef9b1dd1091ed56aa56c9aad3b79b2109e79199223e13a84dd2576',
 'System/procedures/produce-deliverable.md': '8d3e0e9645e6a32ba5fc056a918d5415e90fdbcdbfbc1b5dccf772e7ad4f568b',
 'System/procedures/research-and-summarize.md': 'edc06bbdeb01d264f5fa1426db3df856ce670c97e202ac75b2470002a2aa67d3',
 'System/procedures/review-against-checklist.md': 'c34aa1f8d0ec06510358dcdff06d290239b0d395b566246e4fe83c11775251de',
 'System/procedures/weekly-review.md': 'c742304cc6055fc67b5838b5ff9faa20ca06ca9ff6eca2be1dc1457eddba6dd6',
 'System/procedures/welcome.md': '0a03e51ba37cf7cb24e64a73b3803a43947e08f69c422e18cada86aa26682ef4',
 'CLAUDE.md': '1b7ca4784a39cc170eb7574cd0cc562eac62f64fc0d510de57d65c8499b8151f',
 '.cursor/rules/apparatus.mdc': 'f2d7a240813c5d3438d9d62c8a0981808e782a4ac8dc7275cf010f42c74ea12e',
 '.github/copilot-instructions.md': 'f7ecf9a293035948bb9d12a063c6aa7a81085337d9d65d02ae8a5d42f55f6dcb',
 'System/README.md': 'aa8f93085522ef69ae0624fe07260b0794005c06a4f22774814f8f0bdf680885'}


# Exact PR-38 stock instructions before task-first welcome.
TASK_FIRST_PREVIOUS_INSTRUCTIONS = {'AGENTS.md': '22a54935d5caef2cb6a6c08fb18868541d5a95776787d141aa61e8913154195c',
 'Welcome.md': '9c9612b04aae89667e0f9697d99a9b146dc2ee9f4d143c19dc54534cb1ecad87',
 'System/README.md': '32d22c2e88c1cd3aa49a3dc74b6d54d84bc51c5ed3c96b19e59553796fde911d',
 'System/ignore': '464121144931e07323d94f4e3bf3ab844b277c47eb74184d5aacf4995f7f5a35',
 'CLAUDE.md': '8e7d1fd3cd04eadc419b9efbbce2cb58685bca6a1bbc0341da8d04588400ab2a',
 '.cursor/rules/apparatus.mdc': '76e2ef03f3f8341e26baa87592247065162e5954c8e4f0b439254383376ac45c',
 '.github/copilot-instructions.md': '88453b6b8fcc19ef03c11dcd39b561a58827870f0620199af6e486d74f10a47d',
 '.agents/skills/apparatus-produce-deliverable/SKILL.md': '36a0ec2f178300cbca0a84f0086218940c5ca84a63993897a027e5940e8e349e',
 '.agents/skills/apparatus-research-and-summarize/SKILL.md': '74c29766933a6c14893900bbc4248d988e67b8f36a26b3dfc87373a3d3c4fdbf',
 '.agents/skills/apparatus-review-against-checklist/SKILL.md': 'a18f9cdb8e7b8d0ae0f92a5c24b34c8bc5b64434ac0a55980205e910a15ec7ff',
 '.agents/skills/apparatus-weekly-review/SKILL.md': '84b379d7bbddaed534674740da00ac392032b0c997094818bf3c06a350dc064a',
 '.agents/skills/apparatus-welcome/SKILL.md': 'fb8cd3190c74780f1d5b5defdd68016fb52d64205d52e0aba6be7c86aebf9ed2'}


# Exact PR-39 five-Skill instructions and the original guidance table.
ECONOMY_PREVIOUS_INSTRUCTIONS = {'AGENTS.md': 'da116d700a2814d9e2d45d9dbfa70c5a1b980862e1c4f382eb036fe2d804fb56',
 'Welcome.md': '5bcf362d72d507a8896498d9da83646cc95b8e2b3395cfbbe21b631860048be1',
 'System/README.md': '51ee1850ff9653584142b0b5a789040169bed33ce6f42c0a6c6d8ab984ddb5d6',
 'System/guidance/model-guidance.md': 'dd395ad3d8489f481994cb0635f7b43f0e22fc63085e7b22672257a2a80d893f',
 'CLAUDE.md': '03cfeb0fb3f684b6b280b68b3ecc766c69fa3aed0d5a740750d77ee0da5b9a49',
 '.cursor/rules/apparatus.mdc': '49377d46b123b214ae548ce2c88610c025aaa6dcdc82dc55c586597f6f677b70',
 '.github/copilot-instructions.md': '638dbdf586d356130bdc998a074912e5030ecf519e8673092568987b74e0bdc2'}


# Exact PR-40 seven-Skill stock orientation before learned capture.
LEARNED_PREVIOUS_INSTRUCTIONS = {'AGENTS.md': '9206a676f72452b133efa03e61eccb54644fcbf8365132faa93b955ccffc6a01',
 'Welcome.md': 'a69d8616bcb28bfeda08b0ca15d908945626d4bebc71531631dc1f439b7fe508',
 'System/README.md': '9e0ea94ba15433754a4fde40121293bb1bc4a17efe3ce297d5ddcb3991cfbdb3',
 'CLAUDE.md': 'a50db49ac9a3d301e48bd98fe298e4448a40ca26c097eed2060008b80bf7072d',
 '.cursor/rules/apparatus.mdc': '5739c3f16b221586fb32642113ebf4169c218bbde907ff21d61a094a05daf883',
 '.github/copilot-instructions.md': '1b19dcd5573b5e20116ffbecf823ac7fd5a925374baa2cd2ca480279605e5025'}

# Exact integrated PR-43 stock before cards and completion offers.
CARDS_PREVIOUS_INSTRUCTIONS = {'AGENTS.md': '9c89a64552276fa35ba0419a0fb7c89d22ecfe9439b399274a96dbcd1e833b0e',
 'Welcome.md': 'cd52bfa9c714b9d2b3b9aa835732d7c414c346f0157a44f7f5c3e2a47eb0036b',
 'System/README.md': '9d77710dd6a053040603207a286544e61f7a5e07c0e5add6b9b93361ae73d004',
 '.agents/skills/apparatus-produce-deliverable/SKILL.md': '83c60c29ca5a2324706125b4278850c45561817a82304a41592df3b82784d840',
 '.agents/skills/apparatus-research-and-summarize/SKILL.md': '502e714bf115f276ea75efcb87effe12a978135c6554bd3f225fb7d1313cc7dc',
 'CLAUDE.md': '4db7fa399530b3e427c32e658a5995ac6eedfcc367170a8523f5231b8b3e5243',
 '.cursor/rules/apparatus.mdc': '98cbeb29daa36df30abed7193cae5832a854b78916815bfa7340bf51f40976fa',
 '.github/copilot-instructions.md': 'c87af003b6b071792a7e2e90734b7905ce6f8264d91e266c591d2855268398d2'}

# Exact final PR-44 stock before quiet operations.
QUIET_PREVIOUS_INSTRUCTIONS = {'AGENTS.md': 'ceef205157d9408ae7ed7f318567be3eff99a75be9849a23d665a5d4ee839378',
 'System/README.md': 'c28ad9968b6aef9f3a504eaaee077ee99d287189ec67a605e86cda3284633633',
 'CLAUDE.md': 'eb6554b272112a06d855e8f28ef2495aa007f6be295ceee8719d44576593d006',
 '.cursor/rules/apparatus.mdc': '5347491efd8e5f6bc9130d0f9070c9d79eda6252a336a4f086111df9fc14fb16',
 '.github/copilot-instructions.md': '1f2a7027c045a319c75cde4dd50b018b17faaaeecb04b7d82c8584d43206d50c'}

# Exact PR-49 stock before explicit fact-capture guidance.
EXPLICIT_MEMORY_PREVIOUS_INSTRUCTIONS = {
    'AGENTS.md': '96f7354dde2b8cc07685af724061dfd22b030d743432db89d1fd9f1421a971a8',
}

def _digest(content: bytes) -> str:
    return hashlib.sha256(content.replace(b"\r\n", b"\n")).hexdigest()


def known_instruction(relative: str, content: bytes) -> bool:
    return _digest(content) in {table.get(relative) for table in (
        LEGACY_INSTRUCTIONS, PREVIOUS_INSTRUCTIONS, RETENTION_PREVIOUS_INSTRUCTIONS,
        LAYOUT_PREVIOUS_INSTRUCTIONS, SKILLS_PREVIOUS_INSTRUCTIONS,
        TASK_FIRST_PREVIOUS_INSTRUCTIONS, ECONOMY_PREVIOUS_INSTRUCTIONS,
        LEARNED_PREVIOUS_INSTRUCTIONS, CARDS_PREVIOUS_INSTRUCTIONS, QUIET_PREVIOUS_INSTRUCTIONS,
        EXPLICIT_MEMORY_PREVIOUS_INSTRUCTIONS,
    )}


def has_retired_gate(content: bytes) -> bool:
    text = " ".join(content.decode("utf-8", errors="replace").lower().split())
    return any(marker in text for marker in (
        "apparatus egress", "[share]", "## egress rules",
        "run the egress check", "keep outbound work as a draft",
        "your assistant drafts; you send", "with a cleaned copy offered",
    ))


def has_retired_retention(content: bytes) -> bool:
    text = " ".join(content.decode("utf-8", errors="replace").lower().split())
    if any(marker in text for marker in (
        "task-specific retention control is not available yet",
        "should privacy mode be", "privacy mode (default `standard`)",
    )):
        return True
    return ("block personally identifying content from durable writes under `memory/`"
            in text and "legacy operations before task enrollment" not in text)


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
    instruction_paths = (*LEGACY_INSTRUCTIONS, "System/README.md", "System/guidance/model-guidance.md")
    expected: dict[str, bytes | None] = dict.fromkeys(instruction_paths)
    removals = set(overlay.removals)
    with WorkspaceAnchor(payload) as source:
        proposed: dict[str, bytes] = {}
        for relative in instruction_paths:
            content = _read_optional(source, relative)
            if content is None:
                continue
            proposed[relative] = content
            if has_retired_retention(proposed[relative]):
                raise PayloadError(
                    f"payload instruction {relative!r} has obsolete task retention guidance; "
                    "use the updated starter payload"
                )
            if has_retired_gate(proposed[relative]):
                raise PayloadError(
                    f"payload instruction {relative!r} contains the retired sharing gate; "
                    "use the updated starter payload"
                )
        try:
            native = read_skill_payload(source)
        except ValueError as error:
            raise PayloadError(str(error)) from error
        native_migration = bool(native)
        if native_migration:
            for relative in LEGACY_PROCEDURES:
                expected.pop(relative)
    if workspace.exists():
        with WorkspaceAnchor(workspace) as root:
            for relative in instruction_paths:
                if native_migration and relative in LEGACY_PROCEDURES:
                    continue
                current = _read_optional(root, relative)
                expected[relative] = current
                if current is None:
                    continue
                desired = proposed.get(relative)
                if current == desired:
                    continue
                if known_instruction(relative, current) and desired is not None:
                    if relative not in removals:
                        replacements[relative] = OverlayWrite(relative, desired)
                elif has_retired_retention(current) and not has_retired_gate(current):
                    raise PayloadError(
                        f"custom instruction {relative!r} needs migration; preserve your edits, "
                        "reconcile its Memory rules with the updated task instructions, "
                        "then rerun apparatus init"
                    )
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
    if native_migration:
        with WorkspaceAnchor(workspace) if workspace.exists() else nullcontext(None) as root:
            for relative in native:
                name = BUILTIN_PATHS[relative]
                current = _read_optional(root, relative) if root is not None else None
                expected[relative] = current
                removals.discard(relative)
                if current is not None:
                    if validate_skill(current, name):
                        raise PayloadError(f"canonical Skill {relative!r} is a collision; preserve and reconcile it before retrying init")
                    if known_instruction(relative, current) and current != native[relative]:
                        replacements[relative] = OverlayWrite(relative, native[relative])
                    else:
                        replacements.pop(relative, None)
                else:
                    replacements[relative] = OverlayWrite(relative, native[relative])
            for relative, name in LEGACY_PROCEDURES.items():
                current = _read_optional(root, relative) if root is not None else None
                replacements.pop(relative, None)
                removals.discard(relative)
                if current is None:
                    continue
                expected[relative] = current
                if is_legacy_pointer(relative, current):
                    continue
                if not known_instruction(relative, current):
                    raise PayloadError(
                        f"custom legacy procedure {relative!r} needs migration; preserve your edits, "
                        f"migrate them to {canonical_path(name)!r}, then rerun apparatus init"
                    )
                replacements[relative] = OverlayWrite(relative, legacy_pointer(relative))
    def final_content(relative: str) -> bytes | None:
        if relative in replacements:
            return replacements[relative].content
        current = expected.get(relative)
        return proposed.get(relative) if current is None else current

    canon = final_content("AGENTS.md")
    if canon is not None:
        for shim in rendered_shims_from_bytes(canon):
            current = expected.get(shim.target)
            if current == shim.content:
                replacements.pop(shim.target, None)
            elif current is None or owns_shim(current, shim.target) or known_instruction(shim.target, current):
                replacements[shim.target] = OverlayWrite(shim.target, shim.content)
            else:
                raise PayloadError(
                    f"custom pointer {shim.target!r} conflicts with the final canon; "
                    "preserve and reconcile its instructions before retrying init"
                )
            removals.discard(shim.target)
    return OverlayPlan(
        tuple(replacements.values()),
        tuple(relative for relative in overlay.removals if relative in removals),
    ), expected
