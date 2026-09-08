<!--
Keep a section headed "## v<version>" for every released version. Add the
section in the same change as the version bump; the release pipeline uses it
for GitHub Release notes. Keep unreleased changes below until then.
-->

# Changelog

All notable changes to Apparatus are documented in this file.

## Unreleased

## v0.0.1

Initial pre-alpha release. Apparatus adds portable files and a small toolchain
to local projects; your AI app does the work. It does not call model APIs or
require an Apparatus account.

- Set up a chosen work area or explicitly adopt existing folders, preserving
  project files, repositories, and custom instructions. Bind projects to shared
  context while keeping finished work in each project.
- Recall sourced Memory and correct, mark outdated, or forget People, Facts,
  and Decisions. Task Memory controls suppress automatic capture when requested;
  forgetting does not erase historical backups or control AI-provider retention.
- Register selected Library originals in place, extract supported documents,
  search with citations, and create grounded cards. Missing, changed, and
  partially extracted sources retain explicit coverage limits.
- Include seven portable Skills: task-first welcome, deliverable creation,
  research, on-demand checklist and weekly reviews, economizer, and humanizer.
  Repeated workflows can become editable learned Skills after user review.
  Economizer is guidance, not automatic model switching or a quota limit.
- Snapshot, restore, and export declared managed state without changing project
  Git repositories. Project documents and Library originals are outside this
  recovery coverage. Maintenance reports concrete repair actions.
- Remove the App-specific sharing gate. Ordinary file work follows the user's
  request and the AI app's permissions; existing credential protection remains.
- Provide the `apparatus-core` package with embedded starter files, a separate
  portable payload, Windows and macOS installers, flat setup scripts, and
  release checksums. Public native installers require verified platform signing.
- Require pypdf 6.16.1 or newer for the PDF extraction security fixes included
  during development.

Core needs file reading, file writing, and approved commands. Native Skill
discovery and tested AI-app behavior depend on the particular app and version;
this release does not claim universal certification. Cloud or team Library
services and advanced integrations remain future optional modules.
