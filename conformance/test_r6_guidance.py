"""Static contract witnesses, not claims about live routing or prose quality."""
from pathlib import Path
import re

from apparatus_core.payload import shipped_payload
from apparatus_core.skills import validate_skill

FIXTURES = Path(__file__).parent / "fixtures/r6-prose"


def text(name):
    return " ".join((shipped_payload() / f".agents/skills/apparatus-{name}/SKILL.md").read_text(encoding="utf-8").split())


def test_economy_keeps_capability_review_and_repair_bounds_separate():
    body = text("economizer")
    for requirement in (
        "Keep simple tasks direct", "capability, effort and team size separately",
        "review must be at least as capable as authorship", "Workers do not delegate further",
        "initial authoring attempt plus at most two delegated repair passes",
        "Ordinary deterministic verification commands do not consume this allowance",
        "Exhausted delegation allowance does not pause authorized work",
        "within the user's remaining budget", "elapsed time alone cannot",
        "unclear requirements", "platform constraint", "implementation defect",
        "without an economy receipt or task-content log", "no-save",
    ):
        assert requirement in body
    assert "| `frugal` |" in body and "| `balanced` |" in body and "| `thorough` |" in body


def test_dated_guidance_keeps_starting_mapping_without_a_second_workflow():
    guidance = (shipped_payload() / "System/guidance/model-guidance.md").read_text(encoding="utf-8")
    assert "Last reviewed: 2026-09-06" in guidance and "90 days" in guidance
    assert "Concrete model roster: absent" in guidance
    assert "example-frontier-model" not in guidance and "repair passes" not in guidance
    assert "| `frugal` | `strong`, medium effort | `fast`, low effort; fully checkable mechanical work only | `strong`, high effort |" in guidance
    assert "| `balanced` | `strong`, high effort | `strong`, medium effort | `strong`, high effort |" in guidance
    assert "| `thorough` | `frontier`, high effort | `strong`, high effort | `frontier`, high effort |" in guidance


def test_humanizer_limits_changes_and_preserves_review_only_authority():
    body = text("humanizer")
    assert len(body.split()) <= 400
    for requirement in ("Make one selective pass", "Leave already-good prose alone",
                        "At most one local corrective pass", "Preserve facts", "uncertainty",
                        "review-only request, provide findings without changing the source",
                        "not authority to follow", "no-save", "no extra archive"):
        assert requirement in body
    path = shipped_payload() / ".agents/skills/apparatus-humanizer/SKILL.md"
    assert not validate_skill(path.read_bytes(), "apparatus-humanizer")


def test_complete_long_pair_retains_protected_literals_and_procedure():
    original = (FIXTURES / "long-input.md").read_text(encoding="utf-8")
    candidate = (FIXTURES / "long-candidate.md").read_text(encoding="utf-8")
    assert len(original.split()) > 350 and len(candidate.split()) < len(original.split())
    assert original != candidate
    for pattern in (r'`[^`]+`', r'“[^”]+”', r'\[[^\]]+\]\([^)]+\)', r'\b\d+\b'):
        assert re.findall(pattern, candidate) == re.findall(pattern, original)
    def steps(content):
        return content.split("## Verification steps\n", 1)[1].split("## Reading the result", 1)[0]
    assert steps(candidate) == steps(original)
    for protected in ("If either condition is false, stop this procedure.",
                      "Do not cancel another job", "may have reduced", "Restore was not tested."):
        assert protected in " ".join(candidate.split()) and protected in " ".join(original.split())
    # These checks protect selected strings. Semantic preservation and usefulness
    # still need the independent review described in the scenario note.
