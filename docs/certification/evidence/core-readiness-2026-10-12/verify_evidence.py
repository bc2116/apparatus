"""Offline integrity/consistency check, not a new execution or certification."""
import hashlib
import json
from pathlib import Path
R = Path(__file__).resolve().parent

def load(name):
    return json.loads((R / name).read_text())

def difference(a, b):
    return {'added': sorted(b.keys()-a.keys()), 'removed': sorted(a.keys()-b.keys()),
            'changed': sorted(k for k in a.keys() & b.keys() if a[k] != b[k])}

x = load('results.json')
assert x['result'] == 'pass'
assert x['wheel']['repeated_bytes_equal'] and x['payload']['repeated_bytes_equal']
assert 'pypdf>=6.19.0' in x['wheel']['requires_dist']
assert x['source_sha'] == load('source-changes.json')['candidate_source']
for alias in ('ap', 'apparatus'):
    assert load(alias+'-repeat-before.json') == load(alias+'-repeat-after.json')
a = load('no-save-before.json')
assert a == load('no-save-after-refusal.json')
b = load('no-save-after-requested-note.json')
d = difference(a, b)
assert d == load('no-save-delta.json')
assert d['added'] == ['continuation-area/project/requested-note.md'] and not d['removed']
assert d['changed'] == ['continuation-area/project']
for key in d['changed']:
    assert {k:v for k,v in a[key].items() if k not in ('size','mtime_ns')} == {k:v for k,v in b[key].items() if k not in ('size','mtime_ns')}
for name in ('leaf-link', 'alias-inside'):
    assert load('backup-'+name+'-before.json') == load('backup-'+name+'-after.json')
    assert x['cases']['backup-'+name]['archive_count'] == 0
commands = load('commands.json')
assert len({c['label'] for c in commands}) == len(commands)
expected_errors = {'library-malformed-pdf':1, 'no-save-managed-write-refused':1,
                   'backup-export-leaf-link':2, 'backup-export-alias-inside':2}
for command in commands:
    assert command['return_code'] == expected_errors.get(command['label'],0), command['label']
manifest = load('manifest.json')['files']
actual = {p.relative_to(R).as_posix() for p in R.rglob('*') if p.is_file() and p.name != 'manifest.json'}
assert set(manifest) == actual
for path, sha in manifest.items():
    assert hashlib.sha256((R/path).read_bytes()).hexdigest() == sha, path
print('PASS: captured source-build identity, command outcomes, retention deltas and manifest')
