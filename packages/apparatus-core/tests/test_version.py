from apparatus_core import __version__


def test_version_is_present_and_semver_shaped():
    parts = __version__.split(".")
    assert len(parts) == 3
    assert all(p.isdigit() for p in parts)
