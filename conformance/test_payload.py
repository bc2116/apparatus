from payload_check import PAYLOAD_DIR, diff


CREDENTIAL_FLOOR = (
    "passwords, API keys, tokens, private keys, and high-confidence government "
    "or payment identifiers"
)


def policy_text(mode: str) -> str:
    return (PAYLOAD_DIR / "System" / "policy" / f"{mode}.md").read_text(
        encoding="utf-8"
    )


def test_payload_matches_golden_manifest():
    missing, unexpected = diff()
    assert not missing and not unexpected, (
        f"missing={sorted(missing)} unexpected={sorted(unexpected)} — "
        "if intentional, update the spec and golden manifest in this PR"
    )


def test_policy_overlays_preserve_the_never_relaxed_credential_floor():
    for mode in ("standard", "private"):
        text = policy_text(mode)
        assert "Never relaxed in any mode" in text
        assert CREDENTIAL_FLOOR in text.replace("\n", " ")


def test_policy_overlays_share_identical_credential_and_egress_rules():
    section_marker = "## Credential floor\n"
    standard = policy_text("standard")
    private = policy_text("private")

    assert section_marker in standard and section_marker in private
    assert standard.split(section_marker, 1)[1] == private.split(
        section_marker, 1
    )[1]


def test_policy_overlays_bootstrap_valid_receipts():
    required_receipt_rules = (
        "create `System/receipts/` if it is absent",
        "Markdown record with YAML frontmatter",
        "`schema: apparatus/receipt@v0`",
        "`event: redaction`",
        "`event: egress`",
        "`YYYY-MM-DDTHH:MM:SSZ`",
        "one-sentence `summary`",
        "`YYYY-MM-DD-HHMMSS-<event>.md`",
        "append `-2`, `-3`",
    )

    for mode in ("standard", "private"):
        text = " ".join(policy_text(mode).split())
        for rule in required_receipt_rules:
            assert rule in text
