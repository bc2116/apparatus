from apparatus_core.fs_transactions import (
    _FILE_SHARE_WRITE,
    WindowsIdentity,
    _same_windows_object,
    _win_share_mode,
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
