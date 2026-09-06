<!--
Keep a section headed "## v<version>" for every released version. Add the
section in the same change as the version bump; the release pipeline uses it
for GitHub Release notes. Keep unreleased changes below until then.
-->

# Changelog

All notable changes to Apparatus are documented in this file.

## Unreleased

- Add an isolated recovery backend for the upcoming shared work-area layout.
  Managed snapshots and backups cover declared Apparatus state and recovery
  history without changing root or project Git. Existing starter setup does not
  enable the new layout yet; project documents and Library originals are excluded.

- Add resumable task Memory decisions. No-save tasks suppress new Memory, setup
  answers and automatic capture; requested work files, Library additions and
  backups remain possible. Necessary receipts omit task content, Library recall
  can read without persistence, and snapshot restore preserves live task flags.

- Add current Memory recall and explicit correction, outdated status, and
  forgetting for People and Facts. Legacy records remain current; forgotten
  markers prevent automatic re-seeding at the same path.
- Remove the App-specific sharing gate and command. Repair original legacy
  instructions through `init`, preserving custom conflicts and historical
  receipts. Backup export and credential/filesystem protections are unchanged.
- Initial pre-alpha development.
