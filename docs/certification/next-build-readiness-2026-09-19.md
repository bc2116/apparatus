# Next-build integrated readiness — September 19, 2026

## Decision

Retained source-build acceptance passed for the named candidate. PR delivery
requires current-head CI. This is a narrow N6 outcome, not broad AI-app certification, a
new public release, or native installer, signing, and repair acceptance.

## Candidate and deterministic checks

The candidate is identified by wheel SHA-256
`6284f08fd3fccb63e6fa98cfa236f8b7e219c0aeb796fe861bdabd1f7749ab5c`
and payload identity
`200eb6c5833b1977e9c7927301b7567983ee717d5d250bf47be1b1aa61439a07`.
The built payload archive SHA-256 is
`75dddb640b6433f7241e4e2134013abaf63f3adb349f0434ea4cbdc13e453d34`.
Its identity record enumerates the source inputs and verifies 23 payload files
in the wheel. PR-61's local integrated source suite passed **1469 tests, 42
skipped**, and review passed.

A PR-60 Windows golden-CRLF repair was needed before this record; it was limited
to `.gitattributes`. PR-60 CI passed at `5f64054`, including all Windows safety groups, and
PR-60 merged as `06444fe`. PR-61 CI passed at `8ae64f9`, including all
Windows safety groups, and merged as `6d05582`. Earlier native evidence for [verifiable Memory
saves](evidence/verifiable-memory-2026-09-18/observation.md) and the
[read-only resume brief](evidence/resume-2026-09-18/observation.md) remains
valid only for the dated source candidates and synthetic cases it names.

## What the current native observations show

The refreshed discovery observations used Cursor IDE 3.21.13, GPT-5.6 Luna,
Medium reasoning, Fast off, on macOS 27.0 ARM64, with synthetic fixtures and
one intact prompt per case.

| Case | Result | Evidence boundary |
| --- | --- | --- |
| Work-area root | Pass | The UI showed use of the named witness Skill and opened its exact canonical work-area body. One requested note was added; 68 baseline files were unchanged. |
| Explicitly bound project | Partial | The requested task passed with only its note added and 91 baseline files unchanged. Canonical Skill discovery was not demonstrated. |
| Custom-Skill collision | Partial | The requested task passed with only its note added and 92 baseline files unchanged. Neither marker appeared, so precedence is not established. |
| Non-relevant task | Qualified pass | No irrelevant Skill marker appeared and only the requested inventory was added. Two guessed command paths preceded the supplied executable, so the case retains command-path friction. |

These observations refresh evidence for the named configuration only. They do
not establish automatic discovery across a binding, collision precedence,
provider-internal behavior, or a general adapter requirement. The official
source review in [native discovery evidence](evidence/native-discovery-2026-09-18/sources.md)
remains separate from runtime observations.

## Integrated continuation: pass

The saving conversation persisted a sourced Decision with its reason, updated
the goal next action, registered the selected original, wrote its grounded card,
and took a managed snapshot. The native observation is identified as `96170224`.

A fresh no-save conversation (`8b704c8f`, 31 seconds) named neither the resume
command nor the saved two-page choice. The native UI showed `EXECUTABLE resume PROJECT` select
the explicitly linked work area. Its partial brief reported the registered
retired source as missing and snapshot history unavailable because Git was absent
from the product-process PATH. It used the saved Decision and the current
10-participant, 40-minute details to write the requested participant worksheet.
It cited the relative Decision, brief and outline; equipment, facilitator, date,
and source excerpt remained open. No human reminder was needed.

The before/after comparison shows all 117 baseline files across the work area
and isolated cache byte-for-byte unchanged, including Git and control state; only
`project/participant-worksheet.md` was added and no directory changed. A Markdown
two-page outline was used as context; actual print pagination was not verified.
The archived integrated evidence retains the synthetic prompt, result, candidate
identity, hashes, delta, configuration and stated limitations. This is one native
configuration and does not establish broader Skill behavior or app support.

## Backup alias check

The installed candidate core independently verified backup destination handling.
A canonical external destination and an ordinary system-alias destination each
exited 0 and published one archive. Protected files stayed unchanged; project
files and Library originals were excluded. The command and receipt used the
retained canonical destination. A final destination link and an alias resolving
inside the work area each exited 2 and published no archive. This is a bounded
product-CLI check, not native installer or general filesystem certification.

## Installed-core setup and repair

The same installed wheel provided both `apparatus` and `ap`, initialized a fresh
work area outside the checkout, and left all 64 baseline files unchanged on
repeat init. Removing one generated shim and explicitly running init restored
its exact bytes. Existing files outside managed recovery stayed unchanged;
only the expected repair receipt, snapshot receipt and recovery objects/ref
were added or updated. The first probe's assertion incorrectly expected no
managed writes after an explicit repair; the corrected fresh probe validated
those expected changes without a product modification. This does not exercise
an OS installer wrapper.

## Scope decisions

N4 remains deferred. No early-use observation has established a user need to
relink a moved original; a deliberately missing-source negative fixture is not
that evidence. N5 also remains deferred: missing or partial Skill selection does
not isolate a visibility or adapter need. These are scope decisions, not passing
results for moved-source repair or adapter discovery.

## Delivery and release boundaries

PR-62's own local suite passed 1469 tests with 42 skips in 540.77 seconds
after the standard workspace sync; independent evidence/docs review passed.
PR-60 and PR-61 CI passed on their exact tested heads. PR-62's own current-head
CI is required before merge. The [matrix](matrix.md), plan and
[archived evidence](evidence/integrated-next-build-2026-09-19/run.json) must
agree on the same bounded candidate and coverage.

No installer-wrapper run, signing action, package publication, or public-release
claim was performed for this candidate. Those separate coverage gaps do not
prevent archiving this honest, scoped N6 source-build result. Users evaluating it
do so from a source checkout with its isolated core and payload; the existing
dated release evidence remains the authority for published artifacts.
