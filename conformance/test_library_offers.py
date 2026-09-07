"""Deliberate portable instruction requirements, not a claim of model evaluation."""
from pathlib import Path

PAYLOAD = Path(__file__).parents[1] / 'starter/payload'


def test_completion_offer_is_optional_and_retention_bounded():
    canon = (PAYLOAD / 'AGENTS.md').read_text()
    section = canon.split('## Library cards and completion offers\n', 1)[1].split('\n## ', 1)[0]
    for requirement in ('Skip small drafts', 'already\nselected', 'declining or ignoring',
                        'must not block delivery', 'repeated offers', 'no-save',
                        'Do not save an offer/decline log', 'without acceptance',
                        'never create a card', 'current assistant',
                        'preserve uncertainty', 'known extraction limits',
                        'not original evidence', 'needs no extra approval ritual'):
        assert requirement in section
    assert 'System/skills/adopted/' in canon
    assert canon.count('## Library cards and completion offers') == 1
    for name in ('apparatus-produce-deliverable', 'apparatus-research-and-summarize'):
        body = (PAYLOAD / '.agents/skills' / name / 'SKILL.md').read_text()
        assert 'Library cards and completion offers' in body
        assert 'text_sha256' not in body  # One canonical implementation of the workflow.
