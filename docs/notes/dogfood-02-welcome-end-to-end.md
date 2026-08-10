# Dogfood 02: welcome flow end-to-end

- **Date:** 2026-08-10
- **Scope:** Internal PR-19 dogfood, not app certification.
- **AI app:** Codex.
- **Human terminal commands:** Zero. The assistant ran every command after the
  human requested the bounded PR-19 implementation.

## Story run

The assistant created a fresh temporary workspace with `apparatus init` and
confirmed it with `apparatus check`. It wrote fictional configured interview
answers into `System/profile.yaml`, applied them, and confirmed that two People
records and one Goal record were valid. The profile used standard privacy mode,
a Thursday review cadence, and the balanced spend level.

The assistant filed the fictional reference note in `Library/`, ingested it,
and recalled the cobalt-readiness fact with a citation to
`Library/reference-note.md`. A query for an absent topic returned an explicit
abstention with no citation. The assistant then drafted the readiness brief in
`Projects/`, quoting the cited fact, the fictional person name, and the clearly
fake credential line.

The first egress check stopped without a decision. It enumerated the
People-derived name and the credential, offered a redacted path, wrote only the
required receipts, and did not publish the copy. After the simulated explicit
`use-redacted` choice, a fresh check wrote the redacted copy and decision
receipts. The assistant filed that copy in `Deliverables/`, updated the seeded
Goal to `done` with a next action naming the filed deliverable, took a labeled
snapshot, and finished with a green whole-workspace check.

## Friction observed

| Point | Observation | Disposition |
|---|---|---|
| Scratch path alias | The scratch-directory helper first returned a path whose external ancestor was a symbolic-link alias. `apparatus init` canonicalized it and succeeded, but the first receipt-bearing check rejected the same literal alias and failed closed. | The assistant used the canonical path for the manual pass. Keep the containment rule; add a plan candidate to align command behavior or return the canonical workspace path after initialization. |
| Receipt volume | The complete story creates check receipts in addition to the apply, ingest, recall, egress, redaction, and snapshot receipts named by the PR. | The conformance story validates every receipt present, while binding the milestone receipts to their exact question, source, decision, or snapshot label. |
| Two-pass egress | A credential finding deliberately creates a redaction receipt on both inspection and the fresh decision-bearing run. | Expected behavior; the first records detection and the second records publication without retaining the fake value. |
| Snapshot ordering | The final check necessarily writes a new receipt after the snapshot. | Expected behavior; the job statement requires both a snapshot and a final green check, not a clean implementation store after the check. |

No PR-16, PR-17, or PR-18 integration defect required a core or procedure
change in this pass. The scratch path-alias inconsistency above remains an
explicit follow-up rather than weakening the existing filesystem guardrails.

## Follow-up candidates

- Add this same story to the PR-24 certification checklist for every certified
  AI app, preserving the subprocess-only mechanical proof here.
- In later first-user studies, measure whether the two explicit egress turns
  are clear without exposing command details to the human.
- Specify one cross-command contract for external symbolic-link ancestors:
  either reject them at initialization or return and consistently use the
  canonical workspace path afterward.
