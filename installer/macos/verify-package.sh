#!/usr/bin/env bash

set -Eeuo pipefail
IFS=$'\n\t'

[[ $# -eq 1 ]] || { printf 'Usage: verify-package.sh PACKAGE.pkg\n' >&2; exit 2; }
package=$1
script_directory=$(cd "$(dirname "$0")" && /bin/pwd -P)
bootstrap="$script_directory/bootstrap-apparatus.sh"
postinstall="$script_directory/package-scripts/postinstall"
[[ -f $package && -f $bootstrap && -f $postinstall ]] || {
  printf 'The package verification inputs are incomplete.\n' >&2
  exit 1
}

verify_root=$(mktemp -d "${TMPDIR:-/tmp}/apparatus-package-verify.XXXXXX")
trap 'rm -rf "$verify_root"' EXIT
expanded="$verify_root/expanded"
/usr/sbin/pkgutil --expand-full "$package" "$expanded"
component="$expanded/apparatus-bootstrap.pkg"
scripts="$component/Scripts"
[[ -d $component && -d $scripts && ! -e $component/Payload ]] || {
  printf 'The macOS wrapper must remain a no-payload package.\n' >&2
  exit 1
}

expanded_entries=$(cd "$expanded" && /bin/ls -A | LC_ALL=C sort)
[[ $expanded_entries == $'Distribution\napparatus-bootstrap.pkg' ]] || {
  printf 'The expanded product package contains an unexpected entry.\n' >&2
  exit 1
}
component_entries=$(cd "$component" && /bin/ls -A | LC_ALL=C sort)
[[ $component_entries == $'PackageInfo\nScripts' && -f $component/PackageInfo && \
   ! -L $component/PackageInfo ]] || {
  printf 'The component package contains an unexpected entry.\n' >&2
  exit 1
}
actual_entries=$(cd "$scripts" && /bin/ls -A | LC_ALL=C sort)
expected_entries=$(printf '%s\n' bootstrap-apparatus.sh postinstall | LC_ALL=C sort)
[[ $actual_entries == "$expected_entries" ]] || {
  printf 'The package Scripts archive contains an unexpected entry.\n' >&2
  exit 1
}
[[ -f $scripts/bootstrap-apparatus.sh && ! -L $scripts/bootstrap-apparatus.sh && \
   -f $scripts/postinstall && ! -L $scripts/postinstall ]] || {
  printf 'The package Scripts archive entries must be regular files.\n' >&2
  exit 1
}
cmp "$bootstrap" "$scripts/bootstrap-apparatus.sh"
cmp "$postinstall" "$scripts/postinstall"
printf 'macOS package payload and launcher verified.\n'
