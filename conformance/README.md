# Conformance

Golden fixtures are the executable specification. Each fixture pins an
observable contract of Apparatus — starting with the exact file set of the
universal starter payload — so that drift is a test failure, not a surprise.

Run everything:

```bash
uv run pytest
```

Run just the payload check without any environment (stdlib only):

```bash
python3 conformance/payload_check.py
```

## Fixtures

| Fixture | Pins | Since |
|---|---|---|
| `golden/payload-manifest.txt` | The exact file set of `starter/payload/` against `docs/spec/workspace.md` | PR-03 |
| `golden/records/` | One valid example per record kind against `docs/spec/records.md` and `apparatus_core.records` | PR-04 |

## The rule

Fixtures change only deliberately, in the same PR that intentionally changes
the behavior they pin — with the change called out in the PR description. A
fixture is never loosened to make a failing test pass.
