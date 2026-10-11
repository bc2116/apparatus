"""Compare frozen relative-path inventories; no access to live work-area files."""
import json
import sys
from pathlib import Path

def compare(before, after):
    return {
        'before_entries': len(before),
        'after_entries': len(after),
        'added': sorted(set(after)-set(before)),
        'removed': sorted(set(before)-set(after)),
        'changed': sorted(k for k in set(before)&set(after) if before[k]!=after[k]),
        'unchanged': sum(before[k]==after[k] for k in set(before)&set(after)),
    }

if __name__ == '__main__':
    before=json.loads(Path(sys.argv[1]).read_text())
    after=json.loads(Path(sys.argv[2]).read_text())
    result=compare(before,after)
    print(json.dumps(result,indent=2))
    if len(sys.argv)>3:
        expected=sys.argv[3:]
        if result['changed'] or result['removed'] or result['added'] != sorted(expected):
            raise SystemExit(1)
