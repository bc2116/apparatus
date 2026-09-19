# Verifiable Memory saves — native acceptance

Observed September 18, 2026, America/Los_Angeles, on Cursor IDE 3.21.13,
GPT-5.6 Luna Medium, macOS 27.0 ARM64. Two fresh local chats used the candidate
wheel recorded in [run.json](run.json), through its explicit isolated executable.
Fast mode and other app settings were not observed. No AI CLI, API, global
instruction installation, or inherited test-answer context was used.

## Saving chat

The [ordinary remembering request](prompts/saving.txt) asked for a sourced fact,
a dated Decision and a capacity correction. Cursor found the prepared capacity
fact marked outdated and corrected that existing record to 14, preserving its
source and adding the correction source. It created the handout Decision with
its reason and rejected alternative. The saved [workshop note](results/saving/project/workshop-note.md)
uses 14 places and leaves duration and venue undecided.

Because the initial request correctly reused an existing fact, it did not
exercise new Fact creation. One [distinct follow-up](prompts/saving-followup.txt)
in the same saving chat requested the separate projector fact from the source.
This was additional coverage, not a reworded retry of a failed request.
Both expanded command outputs displayed the existing success sentence followed
by these exact returned locators:

```text
Record: Memory/Decisions/use-printed-handouts-for-lantern-workshop.md
Record: Memory/Facts/lantern-room-has-no-reliable-projector.md
```

Independent inspection confirmed the saved records, the dated Decision schema,
current capacity 14, and the final capacity and Decision content after the follow-up.
See [saving hashes](results/saving/hashes.json) and the retained synthetic records.
The assistant reported managed snapshots; project files remain outside their
recovery scope. Snapshot content coverage is not a new claim in this test.

## Fresh no-save continuation

After freezing the saving results, the operator added an explicitly outdated
synthetic venue proposal and created a no-save task control. These preparation
writes precede the [no-save baseline](results/no-save/before.json). The unrelated
fact remained present. The [fresh prompt](prompts/no-save.txt) supplied no
attendance number, handout answer or venue; it continued that no-save task.

The assistant reformulated an initial no-match query using the task's subject,
used current saved context, and identified the venue record as outdated.
Its [facilitator note](results/no-save/facilitator-note.md) gives 14 places and
printed handouts, includes the reason and saved-record citations, and supplies
no venue or duration. This is a bounded current-Memory continuity result, not
proof of semantic search or populated Library retrieval.

Independent [after hashes](results/no-save/after.json) and
[delta](results/no-save/delta.json) show **all 94 existing work-area files
unchanged**, no cache creation or cache-file changes, and only the requested
project note added. No new Memory, correction, task, receipt, snapshot, Skill
or Library content was written during this chat.

## Limits

This demonstrates only these synthetic requests on this named native variant
and candidate. It does not renew other app/CLI/Windows conversational coverage,
prove native Skill discovery, establish OS confinement or provider retention,
or publish a new release. Deterministic Windows checks are recorded by the PR's
CI; local platform skips are not Windows evidence.
