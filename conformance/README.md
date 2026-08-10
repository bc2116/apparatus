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
| `golden/egress/` | Byte-exact sensitive-content redaction and value-free findings summary | PR-18 |
| `fixtures/welcome-e2e/profile-configured.yaml` | Configured standard-mode interview answers that seed two People records and one Goal | PR-19 |
| `fixtures/welcome-e2e/library/reference-note.md` | One citable fact plus fictional People and credential-floor content for the welcome story | PR-19 |

## The rule

Fixtures change only deliberately, in the same PR that intentionally changes
the behavior they pin — with the change called out in the PR description. A
fixture is never loosened to make a failing test pass.
