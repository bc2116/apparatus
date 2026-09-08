# macOS native acceptance for release 0.0.2

The signed macOS package acceptance for tag `v0.0.2` passed on a hosted ARM64
macOS 15.7.9 runner. Console lookup/session, signature, Gatekeeper,
notarization, install, installed-version, workspace, repair, repaired-version,
and repaired-workspace checks all exited zero. The installed and repaired
version was `0.0.2`; the repaired stock Skill and sentinel hashes are recorded
in `run.json`.

This is evidence for the package install-and-repair workflow. The runner had
preinstalled tools, the wrapper was exercised through the command line, and
administrator-authenticated and standard console-user behavior were not run as
separate cases. It does not establish an interactive GUI result or a desktop
AI-app result. Windows acceptance remains a separate, unclaimed record.
