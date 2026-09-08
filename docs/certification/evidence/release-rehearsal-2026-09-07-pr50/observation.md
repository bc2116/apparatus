# Release rehearsal and ARM64 wrapper observation

The manually dispatched Release workflow completed on source commit
`964d5a1738b2d8928ec85b964474bcc8e59b2316`. It built the payload, source
package, wheel, both flat bootstrap scripts, Windows installer, macOS package,
release notes and checksums. All seven distributable checksums were independently
verified after download. The wheel and payload hashes exactly match the isolated
build used by the app tests. All 80 wheel source/resource files and 23 payload
files matched the reviewed source tree.

Signing, PyPI publishing and GitHub Release creation were skipped. The macOS
package reports `Status: no signature`; stapler validation exited 66. The Windows
installer reports `NotSigned`. This is an unsigned rehearsal, not a public RC.

The downloaded Windows wrapper ran in a Windows 11 ARM64 virtual machine
(OS API version 10.0.26220.0). Its `/DRYRUN /ADOPT` invocation exited 0, verified
the embedded bootstrap hash, recognized the chosen work area outside sync
folders, and described the planned adoption. All 67 existing work-area file
hashes remained unchanged, with no added files. This is a native ARM64 wrapper
dry-run observation; it does not establish a full installation, repair,
Windows x64 acceptance, or an actual desktop-assistant session.

The initial long guest command could not open a Parallels execution session.
Running the same bounded check from a script file succeeded; the cause was not
proved. No VM restart, permission-policy change or signing bypass was used.

The production bootstrap requires `apparatus-core` from PyPI. The public project
endpoint returned HTTP 404 when checked on September 7. Local-wheel installation
and this read-only wrapper run therefore do not satisfy the full installer gate.
