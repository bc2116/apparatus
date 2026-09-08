# Source equivalence for release 0.0.2

The committed-tree comparison from `964d5a1738b2d8928ec85b964474bcc8e59b2316`
to `7a1b0cda634f5d44ff100f83b72fe5e3cc3a4d25`, scoped to
`packages/apparatus-core/src`, `starter`, and `installer`, contains one change:
`apparatus_core.__version__` moves from `0.0.1` to `0.0.2`. No starter or
installer source changed in that scope.

The existing app chats remain evidence for the prior source-equivalent behavior
and retain their `0.0.1` build identity. They were not rerun on `0.0.2` and are
not relabeled as release chats. The 0.0.2 distribution hashes differ from the
prior wheel and payload hashes; both sets are recorded in `run.json`.

The [public GitHub Release](https://github.com/bc2116/apparatus/releases/tag/v0.0.2)
and [PyPI package](https://pypi.org/project/apparatus-core/0.0.2/) were verified on
September 8. All eight GitHub attachments byte-match the signed tagged bundle;
all seven distributable checksums pass. Both native downloads and checksums
return HTTP 200 without authentication. The PyPI wheel and source package match
the same bundle and are not yanked.
