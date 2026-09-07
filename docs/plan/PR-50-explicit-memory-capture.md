# PR-50 — Explicit Memory fact capture

An AI app may create a sourced Library card or plan when asked to remember a
fact without adding a Memory Fact. Add concise starter guidance that makes an
explicit remember/save/keep-durable-fact request a saving-task operation.

## Scope and acceptance

Under **Use current Memory**, direct the AI app to use `apparatus --task ID
memory add-fact WORKSPACE --title TEXT --body TEXT` (or `--from-file`), include
a source reference, verify the record exists, and report its path. A no-save
task must report that the fact was not persisted and needs no extra approval.
Do not add automatic fact capture, change runtime privacy behavior, or alter
the existing command.

Synchronize canonical and embedded starter payloads. Register exact final
PR-49 stock `AGENTS.md` bytes for LF/CRLF migration, while preserving custom
instructions and project files. Keep generated shims current when the render
contract requires it. Focused migration and payload checks plus `uv run pytest`
must pass.

## Verification note

Focused migration coverage proves LF and CRLF stock canon upgrades, custom
canon preservation, and retained task/project bytes. Full-suite results are
recorded with the PR delivery evidence.
