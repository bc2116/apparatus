# PR-32 verification

The sharing command and extra sharing decisions are removed. Original shipped
instructions migrate through `init`; conflicting custom text is preserved with
a repair action. Backup export remains byte-exact, without a sanitization claim.

## Evidence

- `uv sync --all-packages` refreshed the removed command entry point.
- `uv run pytest`: **552 passed, 38 skipped** on macOS. Platform and optional
  dependency skips are not Windows or native AI app certification.
- `uv run python tools/build_payload.py`: payload archive built successfully;
  conformance also checks canonical/embedded bytes and package contents.
- `git diff --check`: passed.
- Deliberate deletions are limited to the retired gate and its dedicated
  fixtures/tests. Credential, backup, transaction, and containment tests remain.

## Review

A bounded authoring-tier implementation team and independent reviewer checked
the policy/migration change. Review found stale-plan races, customized legacy
instructions escaping detection, and mismatched generated pointers. Two repair
passes added regression coverage and preserved custom content. Final review
accepted the change and independently reproduced custom-canon rejection before
mutation, render-and-retry recovery, clean `check`, and preserved custom text.

Initial Windows CI exposed a nested-directory reopen conflict with retained
owned handles during preimage reads. Reads now use the existing immediate
parent anchor. Independent review accepted this bounded platform repair;
the full macOS suite remained green, and a new focused regression simulating
the incompatible reopen passed. Fixture newline conversion also normalizes
Windows checkout bytes before constructing CRLF cases. Actual Windows CI must
pass on the repaired commit before merge.

Migration detects known instruction paths and selected retired phrases; it is
not a semantic audit of arbitrary user-added instructions. Historical sharing
receipts remain readable but grant no authority. Private-profile retention
behavior awaits R2. Remote CI and merge results belong to the pull request.
