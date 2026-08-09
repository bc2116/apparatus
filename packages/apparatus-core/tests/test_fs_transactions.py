import os

import pytest
from apparatus_core import fs_transactions
from apparatus_core.fs_transactions import (
    _FILE_SHARE_WRITE,
    WindowsIdentity,
    WindowsWorkspaceAnchor,
    _same_windows_object,
    _win_share_mode,
)


def test_windows_replace_uses_only_supported_flags(monkeypatch, tmp_path):
    class FakeKernel:
        arguments = None

        def ReplaceFileW(self, *arguments):
            self.arguments = arguments
            return True

    kernel = FakeKernel()
    monkeypatch.setattr(fs_transactions, "_win_kernel", lambda: kernel)

    fs_transactions._win_replace(
        tmp_path / "target.md",
        tmp_path / "replacement.md",
        tmp_path / "backup.md",
    )

    assert kernel.arguments is not None
    assert kernel.arguments[3] == 0


def test_windows_directory_identity_ignores_only_mutable_metadata():
    original = WindowsIdentity(volume=7, index=42, size=0, modified=100)
    metadata_changed = WindowsIdentity(volume=7, index=42, size=12, modified=200)
    replacement = WindowsIdentity(volume=7, index=43, size=0, modified=100)

    assert _same_windows_object(original, metadata_changed)
    assert not _same_windows_object(original, replacement)
    # Regular-file concurrency checks still use complete identity equality.
    assert original != metadata_changed


def test_windows_receipt_alias_shares_only_an_existing_writer():
    retained = _win_share_mode(
        directory=False, lock_name=False, share_existing_write=False
    )
    verification_alias = _win_share_mode(
        directory=False, lock_name=False, share_existing_write=True
    )

    assert not retained & _FILE_SHARE_WRITE
    assert verification_alias & _FILE_SHARE_WRITE


def test_windows_temp_cleanup_deletes_live_handle_before_close(monkeypatch, tmp_path):
    anchor = object.__new__(WindowsWorkspaceAnchor)
    events = []
    monkeypatch.setattr(
        fs_transactions,
        "_win_delete_handle",
        lambda handle: events.append(("delete", handle)),
    )
    monkeypatch.setattr(
        fs_transactions, "_win_close", lambda handle: events.append(("close", handle))
    )

    anchor._discard_created_file(tmp_path / "owned.tmp", 17, None, b"partial")

    assert events == [("delete", 17), ("close", 17)]


def test_windows_temp_cleanup_preserves_substituted_path(monkeypatch, tmp_path):
    anchor = object.__new__(WindowsWorkspaceAnchor)
    owned = WindowsIdentity(volume=1, index=10, size=5, modified=1)
    substitute = WindowsIdentity(volume=1, index=11, size=7, modified=2)
    deleted = []
    closed = []
    monkeypatch.setattr(
        anchor,
        "_read_locked",
        lambda _path: (b"unowned", substitute, 23),
    )
    monkeypatch.setattr(
        fs_transactions, "_win_delete_handle", lambda handle: deleted.append(handle)
    )
    monkeypatch.setattr(
        fs_transactions, "_win_close", lambda handle: closed.append(handle)
    )

    anchor._discard_created_file(tmp_path / "substituted.tmp", -1, owned, b"owned")

    assert deleted == []
    assert closed == [23]


def test_windows_failed_verification_preserves_substituted_backup(
    monkeypatch, tmp_path
):
    anchor = object.__new__(WindowsWorkspaceAnchor)
    target_path = tmp_path / "target.md"
    backup_path = tmp_path / "backup.md"
    target_identity = WindowsIdentity(volume=1, index=20, size=9, modified=1)
    backup_identity = WindowsIdentity(volume=1, index=21, size=8, modified=1)
    substitute_identity = WindowsIdentity(volume=1, index=22, size=9, modified=2)
    state = {
        target_path: b"published",
        backup_path: b"unrelated",
    }
    identities = {
        target_path: target_identity,
        backup_path: substitute_identity,
    }
    matches = []
    replacements = []

    def fake_matches(path, identity, content):
        matches.append((path, identity, content))
        return identities[path] == identity and state[path] == content

    def fake_replace(target, replacement, backup):
        replacements.append((target, replacement, backup))
        state[target] = state[replacement]

    monkeypatch.setattr(anchor, "_matches_path", fake_matches)
    monkeypatch.setattr(fs_transactions, "_win_replace", fake_replace)

    restored = anchor._restore_exact_backup(
        target_path,
        target_identity,
        b"published",
        backup_path,
        backup_identity,
        b"original",
    )

    assert not restored
    assert [match[0] for match in matches] == [target_path, backup_path]
    assert replacements == []
    assert state[target_path] == b"published"
    assert state[backup_path] == b"unrelated"


@pytest.mark.skipif(os.name != "nt", reason="native Win32 transaction regression")
def test_windows_workspace_replace_transaction_commits_and_cleans_backup(tmp_path):
    workspace = tmp_path / "workspace"
    records = workspace / "Memory" / "Facts"
    records.mkdir(parents=True)
    target = records / "fictional.md"
    original = b"original\r\n"
    replacement = b"replacement\r\n"
    target.write_bytes(original)

    anchor = WindowsWorkspaceAnchor(workspace)
    try:
        planned, identity = anchor.read_file("Memory/Facts/fictional.md")
        transaction = anchor.replace_if_unchanged(
            "Memory/Facts/fictional.md",
            identity,
            planned,
            replacement,
        )
        try:
            published, published_identity = anchor.read_file(
                "Memory/Facts/fictional.md"
            )
            assert published == replacement
            assert published_identity == transaction.target.identity
            assert len(list(records.glob(".apparatus-memory-*.bak"))) == 1
            transaction.validate_commit()
            transaction.commit()
        finally:
            transaction.close()
    finally:
        anchor.close()

    assert target.read_bytes() == replacement
    assert not list(records.glob(".apparatus-memory-*.tmp"))
    assert not list(records.glob(".apparatus-memory-*.bak"))
