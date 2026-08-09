from payload_check import diff


def test_payload_matches_golden_manifest():
    missing, unexpected = diff()
    assert not missing and not unexpected, (
        f"missing={sorted(missing)} unexpected={sorted(unexpected)} — "
        "if intentional, update the spec and golden manifest in this PR"
    )
