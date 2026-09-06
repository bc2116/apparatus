# PR-38: Convert built-in procedures to portable Skills

R4a, after PR-36 and its PR-35 recovery dependency. PR-37 independently fixes the
Library lock release race. This branch may prepare work while those dependencies
finish, but must integrate their verified main commits before final validation.
Read ADR-0006, the design brief, workspace/recovery specs and the dated primary
Skill evidence. This cut changes format and migration; native app adapters and
actual discovery probes are R4b, not a completion claim in this PR.

## Result

Keep one regular-file canonical body per built-in Skill under
`.agents/skills/NAME/SKILL.md` at the selected work-area root. Names are:

- `apparatus-welcome`
- `apparatus-produce-deliverable`
- `apparatus-research-and-summarize`
- `apparatus-review-against-checklist`
- `apparatus-weekly-review`

Each replaces the corresponding `System/procedures/<name-without-prefix>.md`.
Use standard YAML `name` and `description`, followed by original readable
instructions. Name must match the directory. Preserve the existing workflow and
retention behavior, changing path/vocabulary references as needed. The welcome
interview redesign is R5; economizer/humanizer additions are R6. Add no scripts,
assets, native options, model executor, Skill registry service or per-install eval.

The work-area canon offers a concise list of when to read these Skills. Do not
load all bodies into the canon. File reading works through the existing explicit
project binding; never infer discovery outside a project's repository boundary.
Keep native app names in compatibility documentation, not in canonical workflow
assumptions. This PR installs no symlinks, global user files or app wrappers.

## Validation and ownership

Add `skills.py` with one explicit built-in mapping (legacy path to Skill name),
path helpers and a portable Skill validator. Require UTF-8, a mapping frontmatter,
unique keys, valid matching name, nonempty description of at most 1024 characters,
and a nonempty readable body. Names are 1-64 lowercase ASCII letters/digits with
single internal hyphens. Accept the common standard optional license,
compatibility, metadata and allowed-tools fields with documented types; these
never grant action authority. Do not require apparatus/<kind> schema in SKILL.md.
Legacy procedure records keep their existing schema and validation for old files
and historical snapshots. Do not rename the old record kind to pretend it is the
native standard.

Do not recursively claim ownership of `.agents/skills`. Only the five exact
canonical paths are built-in managed files in this cut. Other native Skills and
resources stay untouched, unscanned and outside recovery coverage. Validate
present managed Skill files in `check` using their canonical directory names.
Bounded evidence of the new set is any exact built-in directory (even when its
body is missing), a recognized compatibility stub, or exact known shipped
post-migration canon/orientation bytes. These trigger missing-body diagnostics
for the expected five built-ins, with an init repair instruction. Test deletion
of all five bodies, deletion of their directories with known new canon retained,
and an unrelated third-party Skill alone, which must not imply installation.
An entirely legacy work area remains readable; removing every possible marker
of prior installation cannot be distinguished from that legacy state.
Payload conformance proves the complete five-file set for new setup. No new setup
state service or implicit conversion during a read command is needed.

Profile overlays keep their current privacy/work-type selections. Update the
manifest, allowed destinations and selected-workflow path handling together.
Retain legacy procedure-path compatibility for existing manifests/tests. Prefer a
neutral internal workflow-path property over pretending new Skills are procedure
records; keep any necessary compatibility alias small. Customization and exact
preimage protections must apply to new Skill paths too.

## Repeatable migration

Reuse `instruction_updates`, `OverlayPlan`, and retained `deploy_init_plan`
creation/replacement compensation. Plan all affected canonical files, legacy
pointers, canon and app pointers before mutation. Revalidate exact source,
destination, root and layout preimages through final acceptance. Keep profile
answers and task controls unchanged unless their existing explicit command allows
otherwise. A no-save task permits installing generic shipped guidance but no new
user-derived Skill/Memory capture or automatic snapshot.

Recognized original shipped legacy procedures become tiny procedure-schema
compatibility pointers to their canonical Skill. Install those pointers only where
a recognized old file already exists; fresh payloads contain no procedure bodies
or legacy stubs. This preserves old custom-canon references without maintaining
two editable workflow bodies. Recognize exact known LF/CRLF bytes, including
PR-36's current shipped version and the exact new stub. Do not infer ownership
from a filename, header or schema alone. Keep pointer ownership and rollback
preimages exact. Existing unrecognized procedure files remain untouched.

If a customized legacy procedure occupies one of the five migrating paths, stop
preflight with its path and a concise prompt to preserve/migrate that customization
before retrying. Do not silently substitute a stock native Skill for the custom
workflow. If a valid custom canonical Skill already occupies its intended native
path, preserve its bytes and point a recognized old stock file there. Invalid or
foreign canonical occupants are collisions. Preserve custom work-area canon and
unrelated app instructions; known shipped canon/pointers can migrate normally.

Keep readable historic procedure snapshots valid. New managed snapshots, restore
and backup include the exact five canonical Skill files after portable validation,
in addition to compatible legacy records. Update capture, manifest membership and
historic-tree validation together. Other native Skills, optional resources and
project adapter files are excluded; state this limit rather than claiming their
recovery. Restore preserves later additions as before and may restore older
workflow instructions; it does not silently delete stale legacy records. When
new-set evidence coexists with a full legacy procedure at one of the five
migrating paths, `check` reports mixed workflow state and an explicit init/migration
repair instruction. Recognized stubs are healthy; unrelated custom legacy paths
remain ordinary readable records. A pre-migration restore followed by check and
safe re-migration must exercise this diagnostic and preserve every custom file.

## Shared paths and roles

The lead owns `skills.py`, check integration, `overlays.py`, recovery validation/
capture, their focused tests, normative specs and integration. Publish the exact
mapping/validator interface before dependent authors start.

The migration author owns `instruction_updates.py`, narrow init deployment wiring
if needed, and focused migration tests. Use existing transactions, not another
publication framework. Coordinate any changes to shared helper signatures first.

The payload author owns canonical/embedded payload and profile manifests, golden
payload/shim fixtures, and payload/welcome conformance. Preserve workflow semantics
and task controls; adapt native format and references only. Keep source and embedded
copies synchronized. Do not add native adapters in this cut.

Authors are not alone and must preserve other work. Use bounded authoring and
independent review at the migration capability tier; no recursive delegation.
Classify failed assumptions, platform limitations and implementation defects before
retrying. Do not weaken existing filesystem or privacy assertions to pass tests.

## Acceptance and delivery

- New packaged init has exactly five portable built-ins with one editable body
  each and usable file fallback. No legacy procedure body is shipped.
- Upgrading known original instructions creates canonical Skills and exact tiny
  legacy pointers without losing custom canon references. LF/CRLF, no-op repair,
  malformed/custom source/destination conflicts and late publication failures are
  covered with preserved preimages and concurrent content.
- Two bound projects keep one work-area body; no project copies, symlinks, global
  installs or root/project Git changes occur. Existing third-party native Skills
  are unchanged and outside managed capture.
- Overlay selections, checks and recovery understand native Skills. A managed
  archive round trip preserves the declared canonical bytes and usable historical
  procedure snapshots. Unknown resources are not represented as covered.
- No-save installation respects existing task controls and does not automatically
  create snapshots or derived user content. Existing Memory and Library behavior
  passes regression tests.
- Validate positive, malformed and negative cases, canonical/embedded payload,
  full `uv run pytest`, and actual Windows CI. Independent review covers the final
  diff. Status row lands in this PR; normal signed-off branch/PR/CI/remote merge
  rules apply. Do not call R4 complete or claim native app certification yet.
