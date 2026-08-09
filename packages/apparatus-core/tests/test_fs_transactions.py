import os

import pytest
from apparatus_core.fs_transactions import (
    _FILE_SHARE_WRITE,
    WindowsIdentity,
    _same_windows_object,
    _win_close,
    _win_open,
    _win_replace,
    _win_share_mode,
    _win_write,
)


def test_windows_directory_identity_ignores_only_mutable_metadata():
    original = WindowsIdentity(volume=7, index=42, size=0, modified=100)
    metadata_changed = WindowsIdentity(volume=7, index=42, size=12, modified=200)
    replacement = WindowsIdentity(volume=7, index=43, size=0, modified=100)

    assert _same_windows_object(original, metadata_changed)
    assert not _same_windows_object(original, replacement)
    # Regular-file concurrency checks still use complete identity equality.
    assert original != metadata_changed


def test_windows_verification_alias_shares_only_an_existing_writer():
    retained = _win_share_mode(
        directory=False, lock_name=False, share_existing_write=False
    )
    verification_alias = _win_share_mode(
        directory=False, lock_name=False, share_existing_write=True
    )

    assert not retained & _FILE_SHARE_WRITE
    assert verification_alias & _FILE_SHARE_WRITE


@pytest.mark.skipif(os.name != "nt", reason="native Win32 ReplaceFile regression")
def test_windows_replace_accepts_a_retained_invocation_owned_writer(tmp_path):
    target = tmp_path / "target.md"
    replacement = tmp_path / ".apparatus-memory-fictional.tmp"
    backup = tmp_path / ".apparatus-memory-fictional.bak"
    target.write_bytes(b"original")
    target_handle = replacement_handle = -1
    try:
        target_handle = _win_open(target, directory=False, lock_name=False)
        replacement_handle = _win_open(
            replacement,
            directory=False,
            create=True,
            lock_name=False,
            share_existing_write=True,
        )
        _win_write(replacement_handle, b"replacement")
        _win_replace(target, replacement, backup)
    finally:
        _win_close(replacement_handle)
        _win_close(target_handle)

    assert target.read_bytes() == b"replacement"
    assert backup.read_bytes() == b"original"
