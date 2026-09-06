# Staging queue verification

This guide is for the operator of a synthetic staging queue. It is important to
note that this guide applies only to the staging dataset. The purpose of the
following steps is to verify that a paused queue can resume without changing
the production queue. Production recovery is outside this guide's scope.

## Before you begin

Before you begin the verification, first confirm that job-17 is paused and that
no replacement job is active. If either condition is false, stop this procedure.
Do not cancel another job to meet the preconditions. Keep the staged input file
unchanged until verification is complete.

The display may retain an old status for up to 30 s. A stale display alone does
not establish that the worker failed. Compare the current event timestamp with
the displayed status before deciding whether the queue is still paused. The
synthetic timing note describes this limit [Timing note](timing-note.md).

## Verification steps

1. Read the current status with `queue status --job job-17 --environment staging`.
   Save the status in the requested verification document. Do not include the
   contents of the input file.
2. Wait 30 s, then run the same status command again. Continue only if both
   observations show job-17 paused and no replacement job active.
3. Run `queue resume --job job-17 --environment staging --dry-run`. This previews
   the operation. It does not resume processing.
4. Compare the preview with the staged job identifier. If it names any job
   other than job-17, stop. Do not edit the preview to make it match.
5. After the operator approves the preview, run
   `queue resume --job job-17 --environment staging`. Approval for this specific
   operation is a requirement of this synthetic procedure.
6. Observe the next two status events. If the banner says “Do not restart.”,
   leave the queue running and record the warning. Do not restart the worker.
7. If no new event appears within 90 s, stop verification and record the missing
   event. Do not retry the resume command automatically.
8. Record the event identifiers and whether verification completed. If an event
   is missing, report that verification is incomplete rather than successful.

## Reading the result

It is important to note that in 24 synthetic trials the change may have reduced
median wait from 8 s to 6 s [Trial note](trial-note.md). These trials do not show
whether production workloads benefit. Keep that uncertainty in the report.

For clarity, the backup contains four files. Restore was not tested. These
statements belong in the verification document even if the queue resumes.
