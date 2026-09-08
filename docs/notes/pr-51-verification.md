# PR-51 verification

The focused workflow suite passed locally on macOS with Python 3.12 in an
isolated worktree environment:

```text
uv run pytest packages/apparatus-core/tests/test_release_workflow.py -q
13 passed
```

The tests execute the workflow's signing assertion for publish mode with zero,
one, and both successful signers; failed/cancelled signers; and unsigned dry-run
assembly. They verify the protected `release` environment and reject both manual
and tagged dry-run public Release creation. Public creation follows successful
PyPI publication. Dry-run artifacts remain available for rehearsal.

A preliminary full local run was collected before the final dry-run gate change;
its workflow assertions do not establish final-head validation. Required CI runs
the full `uv run pytest` on the final commit and owns platform coverage. The root
review checked the final diff against ADR-0005 and the written acceptance spec;
no core or payload behavior changed and native assistant chats were not repeated.

The release runbook requires signed artifact download and actual per-OS
install-and-repair validation after first PyPI publication and before public
installer approval. This PR is workflow preparation, not evidence of a signed
release, a package upload, or installer acceptance.
