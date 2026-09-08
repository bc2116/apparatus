# PR-54 verification

The baseline [CI run](https://github.com/bc2116/apparatus/actions/runs/34184818702)
completed its Windows safety job in 41m49s. Pytest reported 1,082 passed,
87 skipped, one deselected in 2,479.94 seconds. The five slowest call phases
were recovery scenarios in `test_learned_skills.py` (340.46s),
`test_skill_recovery.py` (262.17s), `test_r6_skills.py` (226.40s),
`test_quiet_operations.py` (142.98s), and `test_library_cards.py` (138.83s).
The split places these across four independent Windows runners.

Parsed old/new workflow comparison confirmed the exact same 54 selectors and
one ETW deselection, with no duplicate or removed selectors. All other existing
jobs remain unchanged. The dedicated bootstrap proof is preserved. The
aggregate retains the required `windows-safety` check name and accepts only
literal success from the matrix; failed, cancelled, skipped, missing, and
unknown results fail its guard.

Focused checks passed (nine tests): the new coverage/gate tests and the
existing hosted-Windows scoped-filesystem proof. Independent frontier review
found no correctness or security issue in the final workflow, tests, and notes.
The full local `uv run pytest` passed: **1286 passed, 38 skipped in 552.14s**.
Live CI timing remains pending; no elapsed-time improvement is claimed yet.
This change adds no app behavior or native AI-app certification claim.
