#!/usr/bin/env bash

set -Eeuo pipefail
IFS=$'\n\t'

usage() {
  printf 'Usage: build-package.sh --output OUTPUT.pkg --version VERSION\n'
}

output=""
version=""
while (($#)); do
  case "$1" in
    --output)
      (($# >= 2)) || { usage >&2; exit 2; }
      output=$2
      shift 2
      ;;
    --version)
      (($# >= 2)) || { usage >&2; exit 2; }
      version=$2
      shift 2
      ;;
    *)
      usage >&2
      exit 2
      ;;
  esac
done

[[ -n $output && -n $version ]] || { usage >&2; exit 2; }
[[ $version =~ ^[0-9]+\.[0-9]+\.[0-9]+([.-][A-Za-z0-9.]+)?$ ]] || {
  printf 'Package version is not valid: %s\n' "$version" >&2
  exit 2
}

script_directory=$(cd "$(dirname "$0")" && /bin/pwd -P)
bootstrap="$script_directory/bootstrap-apparatus.sh"
postinstall="$script_directory/package-scripts/postinstall"
[[ -f $bootstrap && -f $postinstall ]] || {
  printf 'The package inputs are incomplete.\n' >&2
  exit 1
}

output_directory=$(dirname "$output")
mkdir -p "$output_directory"
output_directory=$(cd "$output_directory" && /bin/pwd -P)
output="$output_directory/$(basename "$output")"

build_root=$(mktemp -d "${TMPDIR:-/tmp}/apparatus-package.XXXXXX")
trap 'rm -rf "$build_root"' EXIT
scripts="$build_root/scripts"
mkdir "$scripts"
cp "$postinstall" "$scripts/postinstall"
cp "$bootstrap" "$scripts/bootstrap-apparatus.sh"
chmod 0755 "$scripts/postinstall" "$scripts/bootstrap-apparatus.sh"
cmp "$bootstrap" "$scripts/bootstrap-apparatus.sh"

component="$build_root/apparatus-bootstrap.pkg"
/usr/bin/pkgbuild \
  --nopayload \
  --scripts "$scripts" \
  --identifier org.apparatus.bootstrap \
  --version "$version" \
  "$component"
/usr/bin/productbuild --package "$component" "$output"

"$script_directory/verify-package.sh" "$output"
printf '%s\n' "$output"
