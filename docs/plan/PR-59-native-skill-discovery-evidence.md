# PR-59: Record native Skill discovery evidence

## Purpose

N1 completes the evidence portion of planned R4b before any adapter decision.
PR-38 established one portable canonical Skill body and ordinary file reading;
it did not prove native discovery or invocation. This evidence-only PR observes
whether the current native AI app can discover and follow that one body from a
synthetic work-area root and a separately, explicitly bound synthetic project.
It starts with Codex desktop when it is actually available. An already-authorized
Cursor IDE session is optional. All other variants remain gaps unless the
operator has an authorized native surface at execution time.
The source baseline is `main` at `6ee463d` or its verified remote-main successor
with no behavior changes to Skills. This PR is independent of PR-58; do not
wait for, merge, or rely on PR-58. If the baseline changes before execution,
record the exact commit and explain whether the changed paths affect this probe.

## Scope and owned paths

Create branch `pr-59-native-skill-discovery-evidence`. This PR owns only:

- `docs/certification/evidence/native-discovery-YYYY-MM-DD/inputs/`, containing
  small synthetic work-area and bound-project inputs used by the observed cases;
- `docs/certification/evidence/native-discovery-YYYY-MM-DD/`, containing a
  sanitized run record, prompt files, artifact hashes, and concise observation;
- the narrowly scoped native-discovery row or subsection in
  `docs/certification/matrix.md` that links that record;
- this prompt and its `docs/plan/README.md` status row, if not already added
  by the planning change that cuts this PR.

Replace `YYYY-MM-DD` with the actual observation date once, and use that exact
relative directory in every link. Keep all paths in evidence relative to the
evidence directory or the synthetic work-area root. Do not retain home paths,
account names, conversation identifiers, raw chat logs, screenshots containing
identity, provider metadata beyond the allowed fields below, credentials, or
unsanitized app diagnostics.
Do not modify core, starter payload, adapters, specs, fixtures, installers,
quickstarts, package metadata, workflows, application settings, or user/home
Skill locations. Do not create symlinks, copy a Skill body into a second active
source, install anything in user scope, invoke a model-executing AI CLI or
headless chat probe, use a model API, or spend API credits. Approved Apparatus
commands and ordinary file/hash tools may prepare and inspect the synthetic
fixtures. This is not first-task certification, an
adapter implementation, or a broader support claim.

## Authority and evidence boundary

Read the current official native-Skill discovery documentation at execution
time, then record its URL, retrieval date, and only the path/precedence facts
needed to interpret the observation. The dated local source note is orientation,
not a substitute for this refresh or a runtime result.
Use native in-app work only. Start a **fresh chat** for every case. A current
conversation, restored session, inherited agent context, Skill list, menu,
metadata listing, terminal probe, or an assistant claim that it used a Skill
does not establish discovery. A persisted synthetic file containing distinctive
content from the canonical Skill body, with before/after hashes and semantic
inspection, establishes body use. It does not by itself distinguish native
discovery from ordinary file reading. Record the observed mechanism separately
as native invocation, canon-guided file reading, or unknown. A native-discovery
claim requires app-provided invocation/source evidence as well as the persisted
file; otherwise report body use only and keep native discovery unverified.
A visible menu entry alone does not count.
Use the app's normal, authorized local file permissions. Do not bypass a
permission prompt, change app configuration to expose a global Skills path, or
use a compatibility root merely to make the test pass. If fresh native chats
cannot be isolated or invoked, record `unavailable` with the concrete blocker,
finish the evidence-only PR, and retain the file-reading fallback.

## Synthetic fixture contract

Prepare a minimal non-secret fixture under `inputs/` and copy it only into the
ephemeral work location used by the native app. It contains:

1. `workarea/.agents/skills/apparatus-native-discovery-witness/SKILL.md`, the
   sole canonical body. It has valid portable frontmatter and a distinctive,
   harmless instruction to write one exact witness line to the requested
   project note when the task is relevant. The token must be long and unique,
   for example `APPARATUS-NATIVE-WITNESS-7F3A`, and must not appear in any
   chat prompt, task document, file name, expected-output description, or
   result template.
2. `workarea/` source and sentinel files whose contents are synthetic and whose
   pre-chat hashes are recorded. The requested task must be plausible for the
   Skill description without naming the Skill or its token.
3. `project-bound/`, a separate project explicitly bound to that work area using
   the existing Apparatus binding route. It has its own synthetic task source,
   custom project instructions, sentinel, and one pre-existing user-owned
   Skill with a different body and a recorded SHA-256.
4. A second user-owned `customSkill` whose name collides with the synthetic
   witness name only in the collision case. Record its exact pre/post SHA-256.
   It remains user-owned: changing, deleting, renaming, copying, or replacing
   it is a failure. The canonical witness body remains at the work-area root;
   never place a duplicate body under the project.
Keep fixture sources, expected artifact paths, prompts, and hash manifests in
the record. A sanitized result may quote the synthetic token and file content;
it must not quote general assistant conversation text. Hash the canonical body,
every custom Skill, the task output, and each sentinel before and after each
case. Record intentional output changes separately from all unchanged files.

## Native cases and bounds

For each available variant, attempt the following in order. Run no more than
four fresh chats per variant and no more than one defined platform retry.

1. **Work-area-root, named invocation:** open the synthetic work-area root in a
   fresh native chat. Ask a real, concise project task that invokes the witness
   by its displayed name, without exposing the distinctive token. Verify the
   requested output contains the token from the canonical body and all expected
   sentinels/custom Skills retain their hashes.
2. **Bound-project, relevance invocation:** open only the independently bound
   project in a fresh native chat. Ask the analogous task using no Skill name.
   Its task wording and source must make the witness relevant. Verify the same
   canonical-body oracle, project-local output, work-area and project sentinels,
   and all custom-Skill hashes. A root case never proves this pair.
3. **Duplicate-name collision negative:** use the named collision fixture in a
   fresh chat and request the same relevant task without naming a Skill. Record
   every displayed/discovered candidate if safely observable, which body the
   persisted oracle indicates (if any), and whether both user-owned files remain
   byte-identical. An ambiguity, failure, or absent discovery is evidence, not
   permission to alter user content.
4. **Non-relevant negative:** use a fixture task outside the description's
   relevance. It must not create the witness output or leak the token. Preserve
   all pre-existing hashes. A manually named invocation is not a substitute.
The one retry is available only for a documented platform interruption that
prevents starting or completing a fresh chat (for example, a native app crash
before a prompt is accepted). Repeat the same case once with the same fixture,
record both attempts, and stop. Do not retry a semantic pass/fail, change the
prompt/body/token, add app variants, or turn a negative into a new matrix.
Codex desktop is the first candidate. If it is unavailable to native control or
cannot provide an isolatable fresh chat, document the reason and do not infer
anything from Codex CLI. Cursor IDE may be observed only when an existing,
authorized native IDE is available; record it separately. Claude Code, Codex
CLI, Cursor CLI, Windows, other desktop apps, and untested versions remain
explicit gaps. A Windows row is added only after an authorized native Windows
surface actually completes this same bounded protocol.

## Required record and interpretation

For every attempted pair/case, the sanitized run record states: observation
date/time zone, AI app and exact variant/version, OS/version/architecture,
selected model and effort controls or `unavailable`, relevant app settings or
`unavailable`, fresh-chat method, canonical/custom body hashes, prompt file,
observed artifact paths/hashes, outcome (`pass`, `fail`, `partial`, or
`unavailable`), observed invocation mechanism and its evidence or limitation,
and concise rationale. State which file was inspected to
confirm the token and whether all user-owned custom Skills were preserved.

The evidence note distinguishes named invocation from relevance-triggered
discovery, work-area-root from explicitly bound-project behavior, and discovery
from actual canonical-body invocation. It identifies a future adapter decision
for each tested app/location pair: `justified for focused design`, `not
justified`, or `insufficient evidence; retain fallback`. This PR does not choose
or implement an adapter. No native result changes the required plain-file
fallback, portable canonical format, or one-canonical-body rule.

Update the matrix only with the dated scoped result and explicit gaps. Preserve
all historical CLI/IDE evidence and qualifications; do not relabel it as desktop
evidence or erase failures. Do not call an unavailable row support, certification,
or an absence proof. A pass proves only its named app/version/settings, case,
location pair, and observed canonical-body outcome.

## Acceptance and validation

- The evidence directory contains only synthetic, reviewable inputs and
  sanitized evidence; every internal Markdown link and matrix link resolves.
- The four-case maximum, fresh-chat requirement, single canonical body, no-copy
  rule, distinct root/bound cases, duplicate collision, customSkill hash
  preservation, and non-relevance negative are visibly recorded or an exact
  availability blocker explains why a case did not run.
- Each claimed pass has an independent persisted-file oracle: the unique body
  token was absent from its prompt and inputs other than the canonical body,
  appears in the expected output, and the pre/post hash manifest preserves all
  other synthetic custom Skills and sentinels.
- Exact model/effort/settings observations are recorded when the app exposes
  them; unavailable fields say `unavailable`, never guessed. No raw chats,
  personal data, machine paths, credentials, user-scope install, AI CLI command,
  API call, or app configuration mutation is included.
- Run the smallest document/evidence validation discovered in repository
  guidance, validate JSON/Markdown syntax and relative links, and run any
  existing deterministic fixture validator that applies to these records. Run
  `uv run pytest` before declaring the PR done, as required by this repository.
  Record commands and outcomes; a failed or skipped native case is reported as
  evidence, never repaired by loosening a fixture.
- Set this PR's plan row to `✅ landed` only in the completed evidence PR. Keep
  the diff limited to the owned documentation/evidence paths and the status row.

## Execution roles

A fast model may inventory app metadata and document-link requirements only. A
strong model records the fixture, hashes, and sanitized evidence exactly. A
capable lead accepts the fixture contract, validates the persisted-file oracle,
decides whether each pair supplies sufficient evidence, and reviews the final
diff. The lead must be at least as capable as the recorder. Do not delegate
again, launch an AI CLI, or treat inherited context as a fresh native chat.

## Codex execution prompt

Execute PR-59 on `pr-59-native-skill-discovery-evidence` using this full contract,
the repository instructions, ADR-0006, `docs/spec/skills.md` and the R4b outline
in `docs/plan/rework-sequence.md`. Verify the baseline, prepare only synthetic
fixtures, and observe the bounded cases through available native app surfaces.
Distinguish canonical-body use from evidence of native invocation. Preserve
custom Skills, capture sanitized dated evidence and exact gaps, and update only
the owned evidence, scoped matrix entry and status row. Run the applicable
validation and full suite. If the platform cannot support a valid observation,
finish with an explicit unavailable result and file-reading fallback; do not
invent adapters or retry through an AI CLI. External delivery actions require
the user's actual authorization; this prompt does not grant it.
