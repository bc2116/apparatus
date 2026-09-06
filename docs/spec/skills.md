# Portable Skills

The seven built-in Skills have one regular-file body at the selected work-area
root. Apparatus supplies instructions; the current assistant reads and follows
them. It does not execute Skills or call a model.

| Skill directory | Read when |
|---|---|
| `apparatus-welcome` | Starting or configuring a work area. |
| `apparatus-produce-deliverable` | Producing finished work in its project. |
| `apparatus-research-and-summarize` | Researching with source citations. |
| `apparatus-review-against-checklist` | The user requests a checklist review. |
| `apparatus-weekly-review` | The user requests a weekly review. |
| `apparatus-economizer` | Larger work benefits from native resource choices or bounded delegation. |
| `apparatus-humanizer` | Requested prose editing or a light final pass on an authorized deliverable. |

Each path is `.agents/skills/<directory>/SKILL.md`. A concise work-area canon
index names when to read each body. Bound projects resolve that index through
their explicit work-area link; they do not receive copied Skill bodies.
The five everyday workflows retain task-first behavior. Economy and prose editing
add no setup interview or routine approval gate.

## Format and coverage

Use UTF-8 Markdown with YAML mapping frontmatter delimited by `---`. Required
fields are `name` and `description`. Name matches its directory: 1–64 lowercase
ASCII letters/digits with single internal hyphens. Description is nonempty and
at most 1024 characters. The instruction body is nonempty. Mapping keys must
be unique; recursive aliases and unsupported fields are rejected.

Common optional fields are nonempty string `license`, `compatibility` (at most
500 characters), experimental string `allowed-tools`, and `metadata` mapping
strings to strings. These fields grant no action authority. A Skill has no
`apparatus/procedure@v0` schema; legacy procedure records keep that schema.
Current primary format and discovery sources are recorded in the
[evidence note](../notes/skill-discovery-sources.md).

Only these seven exact paths are managed. Other Skills and optional
scripts, references or assets are neither scanned nor claimed as covered by
Apparatus recovery. Managed capture validates the seven bodies using the same
portable rules as checks and historical snapshot validation.

## Migration and repair

Init validates source and destination files before deployment, then reuses its
retained-root publication and compensation. A native source payload contains either the complete historical five-Skill set
or the complete current seven-Skill set, with no mapped legacy built-in files.
A new built-in directory/body, complete seven-Skill index, or exact shipped
seven-Skill orientation requires all seven bodies, even with an older manifest.
Missing, invalid and mixed sources fail before writes. Entirely legacy custom
payloads and legacy procedure manifests retain compatibility.

Exact known PR-38 native Skill bodies upgrade to the task-first workflows.
Exact PR-39 canon, orientation and original model guidance upgrade to the
seven-Skill version. Valid custom bodies at any of the seven paths stay intact.
Only the five historical procedures have legacy mappings and compatibility
pointers; no old procedure name or stub is invented for the two new Skills.
Known stock Welcome and System orientation files and ignore defaults upgrade
with the same preimage-bound transaction. Customized versions remain untouched.

Exact known shipped legacy procedure bytes, including supported CRLF variants,
become tiny procedure-schema pointers to the canonical body. A pointer is created
only where an old file already exists; fresh setup has no stubs. Existing custom
canon references therefore remain usable. A filename or header alone does not
establish ownership. Customized old built-ins stop migration with a preservation
and repair prompt. Valid custom native bodies remain byte-for-byte unchanged;
invalid or foreign native occupants are collisions. Unrelated files remain intact.

Profile selections retain their existing meaning. Overlay validation accepts
declared legacy procedure paths or these exact native paths; it cannot claim
other native Skills or resources. Custom native bodies survive selection changes.
Installation of generic shipped guidance is permitted during a no-save task;
it does not authorize learned content capture or an automatic snapshot.

Checks use bounded installation evidence: an exact built-in directory, a complete
recognized legacy pointer, or the full shipped Skill index in known orientation
files. With that evidence, missing built-in bodies produce an init repair hint,
including when all bodies have been deleted. Complete historical five-Skill
indexes and exact shipped orientation files remain installation witnesses. An
older five-Skill target receives an actionable upgrade hint for the two missing
new bodies; check remains read-only. An unrelated third-party Skill alone
does not establish installation. Erasing every evidence source cannot be
distinguished from an entirely legacy work area. Ignored known Skill content is
reported as incomplete coverage; it is not silently counted as valid.

Restoring old procedures beside new Skill bodies produces an actionable mixed-state
finding. Checks never delete or migrate files. Init can reconcile recognized stock
files again while preserving custom bodies and stopping on unresolved edits.

## App compatibility

Ordinary file reading is the working baseline. This format migration installs no
symlinks, global user files, native wrappers or app-specific options. Documented
discovery paths are evidence for the next adapter cut, not proof that a particular
app version discovers shared Skills outside its project boundary. Actual native
discovery, duplicate-name behavior and adapter acceptance remain separate checks.

## Task-first everyday work

Welcome starts the actual request with useful defaults and only missing essential
questions. Neither profile status requires a questionnaire or feature menu.
Requested work is checked and saved in its project before optional setup; native
external-action authority and explicit user review constraints still apply.
Research preserves source support and uncertainty without fixed section headings.
Checklist and weekly reviews run only on request; a stored review day is not a
schedule. Snapshot commands own their receipts and report managed-state coverage.

A valid unconfigured or configured profile may receive an explicitly requested
preference change through `profile apply --stdin`. Merge only that change into
the full existing profile, preserving status and unrelated fields. Do not collect
extra answers or seed over existing records, including forgotten markers. Task
Memory controls and credential handling continue to apply; no-save suppresses
profile answers and automatic continuity while requested project files can save.


## Economy and prose boundaries

The [model guidance specification](model-guidance.md) defines portable resource
choices and the data/Skill split. Native controls and live review capability
bound delegation; absent controls leave the capable assistant working directly.
There is no external executor, quota monitor, per-install benchmark or measured
savings claim.

Humanizer makes one selective editing pass, scaled to the request. It compares
changed passages against the source, preserving meaning, facts, numbers/units,
citations and their claim relationships, quotations, identifiers, commands,
negation, conditions, warnings and uncertainty. Uncheckable edits are restored;
at most one local corrective pass is allowed. Good prose stays unchanged.
Review-only requests do not authorize source edits. Source instructions remain
data; editing grants no sending authority. No detector-evasion, authorship
inference, personal voice learning or automatic draft archive is introduced.
No-save still permits requested project prose while blocking automatic derived
retention. Synthetic examples and their evidence limits are recorded in the
[scenario note](../notes/r6-synthetic-scenarios.md).

## Learned workflows

After useful repetition, the assistant may offer a reusable workflow draft. The
user reviews the actual credential-checked file once before adoption. Declining
or ignoring the offer does not delay the original work. No-save tasks neither
offer capture nor store learned drafts; reading adopted Skills remains available.

New capture requires an enrolled work area and an explicit saving task. If absent,
use the existing `apparatus init WORKSPACE --adopt` enrollment action and
`apparatus task start WORKSPACE`; there is no new setup questionnaire.

`apparatus --task ID skill draft WORKSPACE NAME --stdin` accepts a complete portable
Skill with a name beginning `learned-`. It redacts before storing
`System/skill-drafts/NAME.md`, then returns its path and exact SHA-256. Existing
draft files are never overwritten. Show the actual stored bytes for review.
Drafts are inactive, outside native discovery and managed recovery coverage.
Reading a draft for review never authorizes following its instructions.

Only after the user's adoption instruction, run `apparatus --task ID skill adopt
WORKSPACE NAME --digest SHA256`. A changed draft, invalid format or further-needed
credential redaction rejects adoption unchanged; review a safe draft first. The
command never silently sanitizes the reviewed bytes. It publishes one canonical
`.agents/skills/NAME/SKILL.md` and a closed ownership file
`System/skills/adopted/NAME.yaml` in one retained-root transaction. The ownership
YAML has exactly `schema: apparatus/learned-skill@v0` and `name: NAME`; both name
and filename must match, and duplicate keys, aliases and nested values are invalid.
Paths derive from that name rather than user-supplied metadata paths.

Existing native directories, partial pairs and foreign occupants are preserved
with a repair message. Repeat adoption is a no-op only when the draft, digest,
body and valid ownership record agree. The draft stays as an inactive review copy.
Rejected drafts may be deleted explicitly with ordinary file tools. Adopted
bodies remain user-editable; no digest freezes later edits or prompts per use.

The canon points to these small ownership records for fallback discovery; native
adapters may discover the same canonical bodies. Capture never rewrites the canon
or other Skills. No script/asset copying, model calls, routine adoption receipts,
new approval framework or Library registration is provided. Existing redaction
receipts remain required with exact publication compensation.

Checks and managed recovery validate registered body/ownership pairs, including
pairs within each historical manifest. Only exact registered bodies are covered;
prefixes or directory names do not claim unrelated native files. Ignored pairs
produce incomplete-check findings. Missing or invalid pairs prevent capture.
Individual ownership records preserve later adoptions when an older snapshot is
restored. Restore may revive an older adopted workflow; live task controls remain
protected. Drafts and unrelated native files are excluded from managed exports.
Legacy whole-workspace history/backups keep their existing scope and may contain
older drafts or other content; this feature does not sanitize historical copies.
