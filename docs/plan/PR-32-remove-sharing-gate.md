# PR-32: Remove the sharing gate

## Authority and scope

Read `AGENTS.md`, the design brief, ADR-0006, and R1 in
`docs/plan/rework-sequence.md`. Implement R1 only on
`pr-32-remove-sharing-gate`. The owner has approved removing all additional
Apparatus sharing approvals. Do not replace the gate with another prompt or
weaken native authorization, credential redaction, or filesystem protections.

## Implementation contract

1. Remove the `egress` CLI entry point and its unused implementation. There
   are no production callers outside its command adapter. Backup export has
   no runtime dependency on egress: preserve its implementation and byte-exact
   archive contract. Export is not sanitization of historical files.
2. Remove gate instructions, `[share]` markers, required sensitive-item
   decisions, and blanket draft-only restrictions from the canonical payload.
   Preserve user authority for actual external actions, source-as-data,
   credential floor, and existing private-profile Memory rules. Interview,
   central deliverable placement, and procedure-to-Skill conversion wait for
   their own slices. An explicitly requested copy/export needs no second
   Apparatus approval. Core adds no sending integration.
3. Update original legacy instruction files during `init` repair, using a
   bounded allowlist of known shipped content. Preserve custom content;
   detect unresolved legacy instructions and give a concrete repair action
   without claiming successful migration. Do not blindly overwrite custom
   canon, policies, or procedures. Use retained-root transactions and stale
   content checks for replacements, not a read-then-unconditional-write.
   Repeated repair must be safe. Failed/conflicting repair must preserve files.
4. Keep old `event: egress` receipts readable and valid. They are historical
   evidence, never current authorization. Do not emit new egress receipts.
5. Update current workspace/ignore/record specs and IT/user explanations;
   replace the egress spec with a removal/migration note. Historical ADRs,
   landed PR prompts, and old dogfood evidence keep their original scope.
   Reflect R1 completion and the next slice accurately in the plan/README.
6. Synchronize the canonical and embedded starter using the existing tooling.
   Deliberately replace gate conformance tests with absence/native-authority
   and migration checks. Remove only fixtures/tests dedicated to the deleted
   feature; retain shared credential/filesystem/backup regressions and update
   CI references when deleted test paths would otherwise break collection.

## Owned path families

Core entry-point metadata, CLI/egress files, init/deployment and bounded
migration support; targeted init/migration/CLI tests; canonical and embedded
starter; affected conformance; CI test-file references; current specs,
documentation, changelog, and plan. Backup and shared filesystem/credential
implementations should not change without a concrete regression requiring it.

## Acceptance

- Fresh payload/canon/policies contain no active sharing-gate instructions.
  Requested drafting/copy/export has no extra App approval; actual external
  actions still need user/native authority.
- The installed CLI does not expose `egress`. Old receipt records still pass
  record validation; ordinary work emits no new gate decision.
- A known original legacy workspace upgrades without losing records or
  unrelated files; repeat repair is safe. Customized legacy instructions
  produce a precise actionable conflict and are preserved. Exercise stale
  replacement and rollback through existing retained-root primitives.
- Credential, backup, and filesystem safety coverage remains green. No
  assertion that backup removes historical secrets is introduced.
- Run `uv sync --all-packages`, meaningful targeted checks, `uv run pytest`,
  payload embedding/build checks, and `git diff --check`; record platform skips.
- Independent authoring-tier review receives this contract, ADR-0006, and
  the complete diff. PR checks green before merge; verify remote main and
  clean up only this task's branch/worktree. Set this PR's row to `✅ landed`
  in the PR, effective on main after merge.

## Economy and stopping point

Policy/migration work stays at the authoring tier, with bounded independent
assignments and equally capable review. No recursive fan-out. Monitor account
usage between phases; near the remaining-usage limit, leave a committed,
reviewable checkpoint and explicit next step. Never consume a reset implicitly.
