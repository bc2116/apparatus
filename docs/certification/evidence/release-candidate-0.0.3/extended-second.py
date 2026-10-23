"""Additional synthetic installed-candidate checks; no native-app qualification."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--case-name', default='extended-area')
    args = parser.parse_args()
    root = args.run_root.resolve(strict=True)
    output = args.output.resolve()
    assert not output.exists(), 'preserve prior attempts'
    base = Path(__file__).resolve().parents[1] / 'core-readiness-2026-10-12/run.py'
    spec = importlib.util.spec_from_file_location('core_probe', base)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    runtime = root / 'runtime'
    executable = root / 'venv/bin/apparatus'
    env = {key: os.environ[key] for key in ('PATH', 'SYSTEMROOT', 'WINDIR') if key in os.environ}
    env.update(APPARATUS_HOME=str(runtime / 'apparatus-home'),
               PYTHONDONTWRITEBYTECODE='1', LC_ALL='C',
               GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL=os.devnull)
    result = {'scope': 'Synthetic installed CLI checks on POSIX', 'commands': [], 'cases': {}}

    def save():
        text = json.dumps(result, indent=2, sort_keys=True) + '\n'
        for value, alias in ((str(root), '$RUN'), (str(Path.home()), '$HOME')):
            text = text.replace(value, alias)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text)

    def cli(label, *arguments, expected=0):
        completed = subprocess.run([str(executable), *map(str, arguments)],
                                   cwd=runtime / 'external-cwd', env=env,
                                   text=True, capture_output=True, timeout=120)
        result['commands'].append({'label': label, 'argv': list(map(str, arguments)),
                                   'exit': completed.returncode,
                                   'stdout': completed.stdout, 'stderr': completed.stderr})
        save()
        assert completed.returncode == expected, label
        return completed.stdout

    try:
        assert re.fullmatch(r'[a-z0-9-]+', args.case_name)
        area = runtime / args.case_name
        project = area / 'project'
        project.mkdir(parents=True)
        custom = b'# Custom project guidance\r\nKeep the synthetic original.\r\n'
        (area / 'AGENTS.md').write_bytes(custom)
        original = project / 'original.txt'
        original.write_text('Synthetic project original.\n')
        protected = {p: p.read_bytes() for p in (area / 'AGENTS.md', original)}
        before = module.inventory(area)
        cli('reject-implicit-adoption', 'init', area, expected=2)
        assert before == module.inventory(area)
        cli('explicit-adoption', 'init', area, '--adopt')
        cli('adoption-rerun', 'init', area)
        assert all(p.read_bytes() == value for p, value in protected.items())
        assert not (area / '.git').exists()
        result['cases']['adoption'] = {'custom_instructions_and_project_preserved': True,
                                        'implicit_attempt_zero_changes': True}
        task = json.loads(cli('saving-task', 'task', 'start', area, '--save-memory'))['task_id']
        captured = cli('decision-save', '--task', task, 'memory', 'add-decision', area,
                       '--title', 'Synthetic room selection', '--date', '2026-10-23',
                       '--body', 'Use the cobalt room. Source: project/original.txt.')
        record = area / re.search(r'^Record: (.+)$', captured, re.M).group(1)
        record_bytes = record.read_bytes()
        recalled = cli('decision-recall', 'memory', 'recall', area, 'cobalt')
        assert 'cobalt' in recalled.lower() and record.name in recalled
        snapshot = cli('snapshot', '--task', task, 'snapshot', area, '--label', 'Synthetic candidate state')
        snapshot_id = re.search(r'Snapshot id: ([0-9a-f]+)', snapshot).group(1)
        record.write_bytes(record_bytes.replace(b'cobalt', b'violet'))
        original.write_text('Synthetic project work after snapshot.\n')
        no_save = json.loads(cli('no-save-task', 'task', 'start', area, '--no-save'))['task_id']
        control = area / 'System/tasks' / (no_save + '.yaml')
        control_bytes = control.read_bytes()
        cli('managed-restore', 'restore', area, snapshot_id)
        assert record.read_bytes() == record_bytes
        assert original.read_text() == 'Synthetic project work after snapshot.\n'
        assert (area / 'AGENTS.md').read_bytes() == custom
        assert control.read_bytes() == control_bytes
        result['cases']['managed-restore'] = {'memory_restored': True,
                                               'project_custom_instructions_and_live_task_preserved': True}
        source = project / 'reference.md'
        source.write_text('# Synthetic reference\nCopper lantern source marker.\n')
        cli('source-add', '--task', task, 'library', 'add', area, 'project/reference.md')
        first = json.loads(cli('source-search', 'library', 'search', area, 'copper', '--json'))
        assert any(h['source_path'] == 'project/reference.md' for h in first['hits'])
        source.write_text('# Synthetic replacement\nSilver lantern replacement marker.\n')
        before = module.inventory(runtime)
        stale = json.loads(cli('stale-search', '--task', no_save, 'library', 'search',
                               area, 'copper', '--json'))
        assert not stale['hits'] and 'stale' in json.dumps(stale).lower()
        assert module.inventory(runtime) == before
        result['cases']['source-staleness'] = {'stale_hit_suppressed': True,
                                               'no_save_inventory_unchanged': True}
        result['result'] = 'pass'
    except Exception as error:
        result['result'] = 'failed'
        result['failure'] = str(error)
        save()
        raise
    save()
    print('PASS: adoption, Decision recall, managed restore and source staleness')


if __name__ == '__main__':
    main()
