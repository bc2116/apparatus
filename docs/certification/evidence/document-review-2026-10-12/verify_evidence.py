"""Check this captured capsule's integrity and arithmetic, not factual truth."""
import hashlib
import itertools
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent

def read(name):
    return json.loads((ROOT / name).read_text())

def digest(name):
    return hashlib.sha256((ROOT / name).read_bytes()).hexdigest()

def verify():
    commitment = read('oracle-commitment.json')
    assert digest('oracle.json') == commitment['oracle_sha256']
    for path, expected in commitment['cases'].items():
        assert digest(path) == expected, path
    runs = read('runs.json')
    expected = set(itertools.product(['case-01', 'case-02', 'case-03'],
                                    ['current', 'checklist', 'experimental'], [1, 2]))
    assert len(runs) == 18
    assert {(r['case'], r['arm'], r['repetition']) for r in runs} == expected
    assert len({r['id'] for r in runs}) == 18
    for run in runs:
        for kind in ('prompt', 'report'):
            assert digest(run[kind]) == run[kind + '_sha256'], run['id']
        assert run['first_attempt'] and run['correction_attempts'] == 0
        assert run['report_words'] == len((ROOT / run['report']).read_text().split())
    scores = read('scores.json')
    assert scores['oracle_sha256'] == commitment['oracle_sha256']
    assert {r['id'] for r in scores['runs']} == {r['id'] for r in runs}
    assert len(scores['runs']) == 18
    by_id = {r['id']: r for r in runs}
    for score in scores['runs']:
        run = by_id[score['id']]
        assert all(score[k] == run[k] for k in ('case', 'arm', 'repetition', 'report', 'report_sha256'))
        assert {c['claim_id'] for c in score['claims']} == {f'Q{i}' for i in range(1, 7)}
        assert len(score['claims']) == 6
        lines = (ROOT / score['report']).read_text().splitlines()
        for claim in score['claims']:
            assert claim['report_excerpt'] in lines[claim['report_line']-1]
    for arm, total in scores['totals_by_arm'].items():
        selected = [r for r in scores['runs'] if r['arm'] == arm]
        claims = [c for r in selected for c in r['claims']]
        assert total['runs'] == len(selected) == 6
        assert total['claims_expected'] == len(claims) == 36
        assert total['claims_covered'] == sum(c['covered'] for c in claims)
        assert total['material_conclusions_correct'] == sum(c['material_conclusion_correct'] for c in claims)
        assert total['material_issues_expected'] == sum(c['planted_material_issue'] for c in claims) == 16
        assert total['material_issues_caught'] == sum(c['issue_caught'] is True for c in claims)
        assert total['claim_citations_accurate'] == sum(c['source_citation_accurate'] for c in claims)
        assert total['useful_corrections'] == sum(c['useful_correction'] is True for c in claims)
    before, after = read('continuation/before.json'), read('continuation/after.json')
    delta = read('continuation/result.json')
    assert delta['added'] == sorted(set(after)-set(before)) == ['Projects/review/correction-note.md']
    assert delta['removed'] == sorted(set(before)-set(after)) == []
    assert delta['changed'] == sorted(k for k in before.keys() & after.keys() if before[k] != after[k]) == []
    assert delta['unchanged'] == len(before) == 143
    assert len(after) == delta['after_entries'] == 144 and delta['passed']
    note = 'Projects/review/correction-note.md'
    assert digest('continuation/correction-note.md') == after[note]['sha256']
    for path, expected_hash in read('manifest.json')['files'].items():
        assert digest(path) == expected_hash, path
    print('PASS: 18 first outputs, 108 claim scores, committed inputs, and sole requested continuation addition')

if __name__ == '__main__':
    verify()
