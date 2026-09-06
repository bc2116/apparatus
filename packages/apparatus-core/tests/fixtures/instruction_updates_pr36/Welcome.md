# Welcome to your Apparatus workspace

This folder is your workspace: the place where you and your AI assistant keep
your work organized, safe, and easy to pick back up — today, next week, or six
months from now.

**You don't need to learn anything technical.** Talk to your assistant in plain
language. It knows how this workspace is organized and follows its rules.

## What's here

- **Goals** — what you're working toward, each with a clear "done when".
- **Your project folders** — keep each effort's working files and finished
  deliverables together, using your existing folder names.
- **Library** — source documents you drop in. When your assistant uses them,
  it tells you which one it used. If the answer isn't in your Library, it says
  so instead of guessing.
- **Memory** — what your assistant remembers for you: durable facts, and the
  people and organizations you work with. Decisions live in Memory too; existing
  Decisions folders remain readable in place.
- **System** — machinery your assistant uses to keep the rules. You're welcome
  to look; you'll rarely need to.

## Three promises this workspace makes

1. **You direct outside actions.** Your assistant follows your request and your
   AI app's permissions for sending, copying, exporting, or publishing.
   Apparatus adds no extra approval step and provides no sending service.
2. **Credentials are redacted before managed writes.** The existing rules cover
   passwords, API keys, tokens, private keys, and high-confidence government or
   payment identifiers. Personal details are labeled as they are saved. Say
   "don't remember this task" to stop subsequent Memory and automatic capture
   for that task. Requested work files still save normally. Exported backups
   preserve historical files and do not sanitize them.
3. **Snapshots help you recover.** When snapshots are on and the task allows
   automatic saves, the work area can save its managed records and instructions.
   Project files and Library originals are not included. Restoring a snapshot
   preserves later additions and may bring back older Memory. A task's no-save choice survives
   restore; old copies and your AI app's history are not erased.

## Your existing projects

One chosen work area holds Goals, Memory, System and one Library. Your project
folders stay beside them; no enclosing Projects or central Deliverables folder is
required. Your assistant can enroll an existing folder with `apparatus init
WORKAREA --adopt` and connect a project with `apparatus project bind PROJECT
--workspace WORKAREA`. Existing files, instructions and repositories stay in place;
conflicts are reported before a scoped change. Each project points explicitly to
its selected work area, so a nearby folder is never guessed.

## Getting started

Just say hello. If this workspace is new, your assistant will ask you a few
questions about your work — what you do, who you work with, what you're working
on now — and set the workspace up around your answers. The features you choose
are never permanent: re-run my setup interview or just ask your assistant to
change them any time.

Then try it: ask for something real. *"Summarize the document I just put in the
Library"* or *"help me plan this week"* are good first requests.
