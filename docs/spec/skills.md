# Portable Skills

The five built-in workflows have one regular-file body at the selected work-area
root. Apparatus supplies instructions; the current assistant reads and follows
them. It does not execute Skills or call a model.

| Skill directory | Read when |
|---|---|
| `apparatus-welcome` | Starting or configuring a work area. |
| `apparatus-produce-deliverable` | Producing finished work in its project. |
| `apparatus-research-and-summarize` | Researching with source citations. |
| `apparatus-review-against-checklist` | The user requests a checklist review. |
| `apparatus-weekly-review` | The user requests a weekly review. |

Each path is `.agents/skills/<directory>/SKILL.md`. A concise work-area canon
index names when to read each body. Bound projects resolve that index through
their explicit work-area link; they do not receive copied Skill bodies.
The existing workflow steps are preserved in this format migration. Welcome
simplification and new economy/prose guidance have separate implementation cuts.

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

Only these five exact paths are managed in this cut. Other Skills and optional
scripts, references or assets are neither scanned nor claimed as covered by
Apparatus recovery. Managed capture validates the five bodies using the same
portable rules as checks and historical snapshot validation.

## Migration and repair

Init validates source and destination files before deployment, then reuses its
retained-root publication and compensation. A native source payload must contain
all five built-ins and no mapped legacy built-in files. Entirely legacy custom
payloads and legacy procedure manifests retain compatibility.

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
including when all bodies have been deleted. An unrelated third-party Skill alone
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
