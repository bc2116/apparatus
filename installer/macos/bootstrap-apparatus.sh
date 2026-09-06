#!/usr/bin/env bash

set -Eeuo pipefail
IFS=$'\n\t'

readonly SETUP_UV_INSTALL_URL="https://astral.sh/uv/install.sh"
readonly SETUP_UV_INSTALL_REDIRECT_URL="https://releases.astral.sh/installers/uv/latest/uv-installer.sh"
readonly SETUP_UV_RELEASE_SOURCE="https://releases.astral.sh/github/uv/releases/download"
readonly SETUP_UV_RELEASE_FALLBACK="https://github.com/astral-sh/uv/releases/download"
readonly SETUP_PYTHON_SOURCE="https://github.com/astral-sh/python-build-standalone/releases/download"
readonly SETUP_PYPI_INDEX="https://pypi.org/simple"
readonly SETUP_PYPI_FILES="https://files.pythonhosted.org"
readonly SETUP_PYTHON_REQUEST="3.12"

DRY_RUN=0
ADOPT=0
TARGET_INPUT=""

fail() {
  printf 'Apparatus setup stopped: %s\n' "$1" >&2
  printf 'Re-running is safe. See installer/README.md for help.\n' >&2
  exit 1
}

usage() {
  printf 'Usage: bash bootstrap-apparatus.sh [--dry-run] [--path PATH] [--adopt]\n'
}

while (($#)); do
  case "$1" in
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    --adopt)
      ((ADOPT == 0)) || fail "--adopt may be supplied only once."
      ADOPT=1
      shift
      ;;
    --path)
      (($# >= 2)) || fail "--path needs a workspace location."
      TARGET_INPUT=$2
      shift 2
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      fail "Unknown option: $1"
      ;;
  esac
done

((BASH_VERSINFO[0] >= 3)) || fail "Bash 3 or newer is required."
[[ -x /usr/bin/uname ]] || fail "The operating-system check is unavailable."
[[ "$(/usr/bin/uname -s)" == "Darwin" ]] || fail "This script supports macOS only."
[[ -n ${HOME:-} && $HOME == /* && -d $HOME && ! -L $HOME ]] || \
  fail "The user profile is missing, relative, or redirected."

physical_pwd=$(/bin/pwd -P) || fail "The current folder could not be resolved."
if [[ -z $TARGET_INPUT ]]; then
  target="$HOME/Projects"
elif [[ $TARGET_INPUT == "~" ]]; then
  target=$HOME
elif [[ $TARGET_INPUT == "~/"* ]]; then
  target="$HOME/${TARGET_INPUT:2}"
elif [[ $TARGET_INPUT == /* ]]; then
  target=$TARGET_INPUT
else
  target="$physical_pwd/$TARGET_INPUT"
fi

[[ $target != *$'\n'* && $target != *$'\r'* ]] || \
  fail "The workspace location contains unsupported characters."

lexically_normalize_absolute() {
  local input=$1 remaining=${1#/} part output=""
  [[ $input == /* ]] || return 1
  while [[ -n $remaining ]]; do
    case $remaining in
      */*) part=${remaining%%/*}; remaining=${remaining#*/} ;;
      *) part=$remaining; remaining="" ;;
    esac
    case $part in
      ""|.) continue ;;
      ..) return 1 ;;
      *) output="$output/$part" ;;
    esac
  done
  printf '%s' "${output:-/}"
}

target=$(lexically_normalize_absolute "$target") || \
  fail "The workspace location must not contain '..' components."

check_no_symlink_components() {
  local path=$1 current="" part remaining=${1#/}
  while [[ -n $remaining ]]; do
    case $remaining in
      */*) part=${remaining%%/*}; remaining=${remaining#*/} ;;
      *) part=$remaining; remaining="" ;;
    esac
    [[ -n $part && $part != . ]] || continue
    current="$current/$part"
    if [[ -L $current ]]; then
      return 1
    fi
  done
  return 0
}

target_safe=1
target_reason="outside iCloud Drive"
if ! check_no_symlink_components "$target"; then
  target_safe=0
  target_reason="blocked: the location passes through a symbolic link"
fi
icloud=$(lexically_normalize_absolute "$HOME/Library/Mobile Documents") || \
  fail "The iCloud Drive boundary could not be normalized."
case "$target/" in
  "$icloud/"*)
    target_safe=0
    target_reason="blocked: the location is inside iCloud Drive"
    ;;
esac

readonly SETUP_UV_BIN="$HOME/.local/bin/uv"
readonly SETUP_UV_PYTHON_DIR="$HOME/.local/share/uv/python"
readonly SETUP_UV_TOOL_DIR="$HOME/.local/share/uv/tools"
readonly SETUP_UV_TOOL_BIN="$HOME/.local/bin"
readonly SETUP_UV_CACHE_DIR="$HOME/.cache/uv"
readonly APPARATUS_BIN="$SETUP_UV_TOOL_BIN/apparatus"

find_uv() {
  if [[ -x $SETUP_UV_BIN && ! -d $SETUP_UV_BIN ]] && \
      check_no_symlink_components "$SETUP_UV_BIN"; then
    printf '%s' "$SETUP_UV_BIN"
    return 0
  fi
  return 1
}

find_git() {
  local candidate version
  candidate=$(type -P git || true)
  [[ -n $candidate && -x $candidate && ! -d $candidate ]] || return 1
  check_no_symlink_components "$candidate" || return 1
  version=$(
    PATH=/usr/bin:/bin:/usr/sbin:/sbin BASH_ENV= ENV= \
      "$candidate" --version 2>&1
  ) || return 1
  [[ $version == "git version "* ]] || return 1
  printf '%s' "$candidate"
}

managed_python_present() {
  local candidate
  for candidate in "$SETUP_UV_PYTHON_DIR"/cpython-3.12*; do
    [[ -d $candidate && ! -L $candidate ]] && return 0
  done
  return 1
}

state_line() {
  printf '  %-18s %s\n' "$1:" "$2"
}

uv_path=$(find_uv || true)
git_path=$(find_git || true)
if ((DRY_RUN)); then
  printf 'Apparatus setup dry-run (read-only detection; no install, network, or workspace commands)\n'
  state_line "Operating system" "present (macOS)"
  if ((target_safe)); then
    state_line "Target safety" "present ($target; $target_reason)"
  else
    state_line "Target safety" "missing ($target; $target_reason)"
  fi
  [[ -n $uv_path ]] && state_line "uv" "present" || state_line "uv" "missing (install planned)"
  managed_python_present && state_line "Managed Python" "present" || state_line "Managed Python" "missing (install planned)"
  [[ -n $git_path ]] && state_line "Git" "present" || state_line "Git" "missing (capability unconfirmed; continue planned)"
  [[ -x $APPARATUS_BIN && ! -d $APPARATUS_BIN ]] && state_line "Apparatus tool" "present (upgrade planned)" || state_line "Apparatus tool" "missing (install planned)"
  if ((target_safe)); then
    state_line "Workspace" "planned (core validation and repair; existing nonempty folders require --adopt)"
  else
    state_line "Workspace" "missing (blocked until a safe target is chosen)"
  fi
  ((ADOPT)) && state_line "Adoption" "planned (explicitly requested)"
  ((target_safe)) && state_line "Doctor" "planned (report verification follows)" || state_line "Doctor" "planned after target repair"
  state_line "Network" "planned only for missing/upgrade steps from approved sources"
  exit 0
fi

if ((!target_safe)); then
  if [[ $target_reason == *"iCloud Drive"* ]]; then
    fail "The workspace cannot be inside iCloud Drive. Live workspace state must not sit in a sync engine; use one-way snapshot export for backup."
  fi
  fail "The workspace location passes through a symbolic link."
fi

if [[ -e $target && ! -d $target ]]; then
  fail "The workspace location exists and is not a folder."
fi

for user_scope_path in \
    "$HOME" "$SETUP_UV_BIN" "$SETUP_UV_PYTHON_DIR" "$SETUP_UV_TOOL_DIR" \
    "$SETUP_UV_TOOL_BIN" "$SETUP_UV_CACHE_DIR"; do
  check_no_symlink_components "$user_scope_path" || \
    fail "A user-scope tool location passes through a symbolic link."
done

# Ignore caller-provided uv, pip, and Python configuration before setting the
# small environment needed by this invocation.
while IFS= read -r poison_name; do
  unset "$poison_name"
done < <(compgen -e | /usr/bin/grep -E '^(UV_|PIP_|PYTHON)')
export UV_INSTALL_DIR="$HOME/.local/bin"
export UV_PYTHON_INSTALL_DIR="$SETUP_UV_PYTHON_DIR"
export UV_TOOL_DIR="$SETUP_UV_TOOL_DIR"
export UV_TOOL_BIN_DIR="$SETUP_UV_TOOL_BIN"
export UV_CACHE_DIR="$SETUP_UV_CACHE_DIR"
export UV_DEFAULT_INDEX="$SETUP_PYPI_INDEX" UV_NO_CONFIG=1
export UV_MANAGED_PYTHON=1 UV_PYTHON_INSTALL_MIRROR="$SETUP_PYTHON_SOURCE"
export UV_NO_MODIFY_PATH=1
unset INSTALLER_DOWNLOAD_URL VIRTUAL_ENV

if [[ -n $uv_path ]] && ! "$uv_path" --version >/dev/null 2>&1; then
  uv_path=""
fi

if [[ -z $uv_path ]]; then
  [[ -x /usr/bin/curl ]] || fail "curl is required to install uv."
  printf 'Installing uv in your user profile...\n'
  if ! /usr/bin/curl -q --proto '=https' --tlsv1.2 -LsSf "$SETUP_UV_INSTALL_URL" | \
      /usr/bin/env -i HOME="$HOME" PATH=/usr/bin:/bin:/usr/sbin:/sbin \
        UV_INSTALL_DIR="$UV_INSTALL_DIR" UV_NO_MODIFY_PATH=1 \
        BASH_ENV= ENV= /bin/sh; then
    fail "uv could not be installed. A download or device policy may be blocking it."
  fi
  uv_path=$SETUP_UV_BIN
fi
[[ -x $uv_path && ! -d $uv_path ]] || fail "uv is not available after installation."

run_uv() {
  if ! "$uv_path" "$@"; then
    fail "A required user-scope tool step failed. A download or device policy may be blocking it."
  fi
}

managed_python_ready() {
  managed_python_present && \
    "$uv_path" python find --no-config --managed-python "$SETUP_PYTHON_REQUEST" \
      >/dev/null 2>&1
}

if managed_python_ready; then
  printf 'Managed Python is present.\n'
else
  printf 'Installing managed Python...\n'
  run_uv python install --no-config --managed-python \
    --mirror "$SETUP_PYTHON_SOURCE" "$SETUP_PYTHON_REQUEST"
fi

if [[ -n $git_path ]]; then
  printf 'Git is present; snapshots can be checked.\n'
else
  printf 'Git was not confirmed by the initial probe. Doctor will report actual snapshot capability.\n'
fi

if [[ -x $APPARATUS_BIN && ! -d $APPARATUS_BIN ]]; then
  printf 'Checking for an Apparatus update...\n'
  run_uv tool upgrade --no-config --default-index "$SETUP_PYPI_INDEX" apparatus-core
else
  printf 'Installing Apparatus from PyPI...\n'
  run_uv tool install --no-config --managed-python \
    --default-index "$SETUP_PYPI_INDEX" apparatus-core
fi
[[ -x $APPARATUS_BIN && ! -d $APPARATUS_BIN ]] || \
  fail "The Apparatus command is missing after installation."

doctor_path="$SETUP_UV_TOOL_BIN:/usr/bin:/bin:/usr/sbin:/sbin"
if [[ -n $git_path ]]; then
  git_directory=${git_path%/*}
  case ":$doctor_path:" in
    *":$git_directory:"*) ;;
    *) doctor_path="$SETUP_UV_TOOL_BIN:$git_directory:/usr/bin:/bin:/usr/sbin:/sbin" ;;
  esac
fi
export PATH=$doctor_path

printf 'Validating the chosen work area and repairing recognized shipped content...\n'
init_options=("$target")
((ADOPT)) && init_options+=(--adopt)
if ! "$APPARATUS_BIN" init "${init_options[@]}"; then
  printf 'If core requests adoption and you want to enroll this folder, run the released script:\n' >&2
  printf '  /usr/bin/env -u BASH_ENV -u ENV /bin/bash bootstrap-apparatus.sh --path %q --adopt\n' "$target" >&2
  fail "Core init stopped. Follow its diagnostic; check target permissions if it is not writable. Existing deployment may remain when a later snapshot failed."
fi

check_report_boundary() {
  check_no_symlink_components "$target" || return 1
  [[ -d $target/System && ! -L $target/System ]] || return 1
  [[ ! -e $target/System/machine-report.md && ! -L $target/System/machine-report.md ]] || \
    [[ -f $target/System/machine-report.md && ! -L $target/System/machine-report.md ]]
}

check_report_boundary || fail "The workspace report path is redirected or unsafe."
set +e
"$APPARATUS_BIN" doctor "$target"
doctor_status=$?
set -e
check_report_boundary && [[ -f $target/System/machine-report.md ]] || \
  fail "The workspace report path changed during doctor."

report=$target/System/machine-report.md
report_fields=""
report_closed=0
{
  IFS= read -r report_line || fail "Doctor returned an empty report."
  [[ $report_line == '---' ]] || fail "Doctor returned malformed report frontmatter."
  while IFS= read -r report_line; do
    if [[ $report_line == '---' ]]; then
      report_closed=1
      break
    fi
    report_fields+="$report_line"$'\n'
  done
} < "$report"
((report_closed)) || fail "Doctor returned unclosed report frontmatter."
reported_uv=$(printf '%s' "$report_fields" | /usr/bin/grep '^uv:' || true)
uv_version_pattern='^uv: "[^"[:cntrl:]]+"$'
if [[ ! $reported_uv =~ $uv_version_pattern ]]; then
  fail "Doctor did not confirm the installed user-scope toolchain."
fi
reported_risk=$(printf '%s' "$report_fields" | /usr/bin/grep '^  at_risk:' || true)
if [[ $reported_risk != '  at_risk: false' ]]; then
  fail "Doctor reported that the workspace is inside a sync engine."
fi
reported_git=$(printf '%s' "$report_fields" | /usr/bin/grep '^git:' || true)
reported_snapshots=$(printf '%s' "$report_fields" | /usr/bin/grep '^snapshots:' || true)
git_version_pattern='^git: "[^"[:cntrl:]]+"$'
if [[ $reported_git == 'git: null' && $reported_snapshots == 'snapshots: "unavailable"' ]]; then
  [[ $doctor_status -eq 0 || $doctor_status -eq 1 ]] || \
    fail "Doctor could not complete capability detection."
  printf 'Snapshots are unavailable. Make Git available to your AI app, then rerun setup.\n'
elif [[ $reported_git =~ $git_version_pattern && $reported_snapshots == 'snapshots: "available"' ]]; then
  [[ $doctor_status -eq 0 ]] || fail "Doctor found a blocked or incomplete toolchain."
else
  fail "Doctor returned inconsistent Git and snapshot capability fields. Rerun doctor and inspect its report."
fi

printf 'Apparatus is ready at %s. Open this work area in your AI app and ask for your actual task; Welcome.md explains the available help.\n' "$target"
