#!/usr/bin/env bash

set -Eeuo pipefail
IFS=$'\n\t'

readonly UV_INSTALL_URL="https://astral.sh/uv/install.sh"
readonly UV_INSTALL_REDIRECT_URL="https://releases.astral.sh/installers/uv/latest/uv-installer.sh"
readonly UV_RELEASE_SOURCE="https://releases.astral.sh/github/uv/releases/download"
readonly UV_RELEASE_FALLBACK="https://github.com/astral-sh/uv/releases/download"
readonly PYTHON_SOURCE="https://github.com/astral-sh/python-build-standalone/releases/download"
readonly PYPI_INDEX="https://pypi.org/simple"
readonly PYPI_FILES="https://files.pythonhosted.org"
readonly PYTHON_REQUEST="3.12"

DRY_RUN=0
TARGET_INPUT=""

fail() {
  printf 'Apparatus setup stopped: %s\n' "$1" >&2
  printf 'Re-running is safe. See installer/README.md for help.\n' >&2
  exit 1
}

usage() {
  printf 'Usage: bash bootstrap-apparatus.sh [--dry-run] [--path PATH]\n'
}

while (($#)); do
  case "$1" in
    --dry-run)
      DRY_RUN=1
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
  target="$HOME/Projects/Apparatus"
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
case "/${target#/}/" in
  */../*) fail "The workspace location must not contain '..' components." ;;
esac
while [[ $target != / && $target == */ ]]; do target=${target%/}; done

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
icloud="$HOME/Library/Mobile Documents"
case "$target/" in
  "$icloud/"*)
    target_safe=0
    target_reason="blocked: the location is inside iCloud Drive"
    ;;
esac

readonly UV_BIN="$HOME/.local/bin/uv"
readonly UV_PYTHON_DIR="$HOME/.local/share/uv/python"
readonly UV_TOOL_DIR="$HOME/.local/share/uv/tools"
readonly UV_TOOL_BIN="$HOME/.local/bin"
readonly UV_CACHE_DIR="$HOME/.cache/uv"
readonly APPARATUS_BIN="$UV_TOOL_BIN/apparatus"

find_uv() {
  if [[ -x $UV_BIN && ! -d $UV_BIN ]] && \
      check_no_symlink_components "$UV_BIN"; then
    printf '%s' "$UV_BIN"
    return 0
  fi
  return 1
}

managed_python_present() {
  local candidate
  for candidate in "$UV_PYTHON_DIR"/cpython-3.12*; do
    [[ -d $candidate && ! -L $candidate ]] && return 0
  done
  return 1
}

workspace_present() {
  local relative
  local required_files=(
    AGENTS.md CLAUDE.md Welcome.md
    .cursor/rules/apparatus.mdc .github/copilot-instructions.md
    System/README.md System/profile.yaml System/ignore
    System/guidance/model-guidance.md
    System/policy/private.md System/policy/standard.md
    System/procedures/welcome.md
    System/procedures/produce-deliverable.md
    System/procedures/research-and-summarize.md
    System/procedures/review-against-checklist.md
    System/procedures/weekly-review.md
  )
  local required_directories=(
    Goals Decisions Projects Library Deliverables Memory/People Memory/Facts
    System/receipts
  )
  [[ -d $target && ! -L $target ]] || return 1
  for relative in "${required_files[@]}"; do
    [[ -f $target/$relative && ! -L $target/$relative ]] || return 1
  done
  for relative in "${required_directories[@]}"; do
    [[ -d $target/$relative && ! -L $target/$relative ]] || return 1
  done
  return 0
}

state_line() {
  printf '  %-18s %s\n' "$1:" "$2"
}

uv_path=$(find_uv || true)
git_path=$(type -P git 2>/dev/null || true)
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
  [[ -n $git_path ]] && state_line "Git" "present" || state_line "Git" "missing (snapshots unavailable; continue planned)"
  [[ -x $APPARATUS_BIN && ! -d $APPARATUS_BIN ]] && state_line "Apparatus tool" "present (upgrade planned)" || state_line "Apparatus tool" "missing (install planned)"
  if ((target_safe)) && workspace_present; then
    state_line "Workspace" "present (init skip planned)"
  elif ((target_safe)); then
    state_line "Workspace" "missing (non-destructive init planned)"
  else
    state_line "Workspace" "missing (blocked until a safe target is chosen)"
  fi
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
    "$HOME" "$UV_BIN" "$UV_PYTHON_DIR" "$UV_TOOL_DIR" \
    "$UV_TOOL_BIN" "$UV_CACHE_DIR"; do
  check_no_symlink_components "$user_scope_path" || \
    fail "A user-scope tool location passes through a symbolic link."
done

# Ignore caller-provided uv, pip, and Python configuration before setting the
# small environment needed by this invocation.
while IFS= read -r poison_name; do
  unset "$poison_name"
done < <(compgen -e | /usr/bin/grep -E '^(UV_|PIP_|PYTHON)')
export UV_INSTALL_DIR="$HOME/.local/bin"
export UV_PYTHON_INSTALL_DIR="$UV_PYTHON_DIR"
export UV_TOOL_DIR="$UV_TOOL_DIR"
export UV_TOOL_BIN_DIR="$UV_TOOL_BIN"
export UV_CACHE_DIR="$UV_CACHE_DIR"
export UV_DEFAULT_INDEX="$PYPI_INDEX" UV_NO_CONFIG=1
export UV_MANAGED_PYTHON=1 UV_PYTHON_INSTALL_MIRROR="$PYTHON_SOURCE"
export UV_NO_MODIFY_PATH=1
unset INSTALLER_DOWNLOAD_URL VIRTUAL_ENV

if [[ -n $uv_path ]] && ! "$uv_path" --version >/dev/null 2>&1; then
  uv_path=""
fi

if [[ -z $uv_path ]]; then
  [[ -x /usr/bin/curl ]] || fail "curl is required to install uv."
  printf 'Installing uv in your user profile...\n'
  if ! /usr/bin/curl -q --proto '=https' --tlsv1.2 -LsSf "$UV_INSTALL_URL" | \
      /usr/bin/env UV_INSTALL_DIR="$UV_INSTALL_DIR" UV_NO_MODIFY_PATH=1 /bin/sh; then
    fail "uv could not be installed. A download or device policy may be blocking it."
  fi
  uv_path=$UV_BIN
fi
[[ -x $uv_path && ! -d $uv_path ]] || fail "uv is not available after installation."

run_uv() {
  if ! "$uv_path" "$@"; then
    fail "A required user-scope tool step failed. A download or device policy may be blocking it."
  fi
}

managed_python_ready() {
  managed_python_present && \
    "$uv_path" python find --no-config --managed-python "$PYTHON_REQUEST" \
      >/dev/null 2>&1
}

if managed_python_ready; then
  printf 'Managed Python is present.\n'
else
  printf 'Installing managed Python...\n'
  run_uv python install --no-config --managed-python \
    --mirror "$PYTHON_SOURCE" "$PYTHON_REQUEST"
fi

if [[ -n $git_path ]]; then
  printf 'Git is present; snapshots can be checked.\n'
else
  printf 'Git was not found. Setup will continue and doctor will record snapshots as unavailable.\n'
fi

if [[ -x $APPARATUS_BIN && ! -d $APPARATUS_BIN ]]; then
  printf 'Checking for an Apparatus update...\n'
  run_uv tool upgrade --no-config --default-index "$PYPI_INDEX" apparatus-core
else
  printf 'Installing Apparatus from PyPI...\n'
  run_uv tool install --no-config --managed-python \
    --default-index "$PYPI_INDEX" apparatus-core
fi
[[ -x $APPARATUS_BIN && ! -d $APPARATUS_BIN ]] || \
  fail "The Apparatus command is missing after installation."

doctor_path="$UV_TOOL_BIN:/usr/bin:/bin:/usr/sbin:/sbin"
if [[ -n $git_path ]]; then
  git_directory=${git_path%/*}
  case ":$doctor_path:" in
    *":$git_directory:"*) ;;
    *) doctor_path="$UV_TOOL_BIN:$git_directory:/usr/bin:/bin:/usr/sbin:/sbin" ;;
  esac
fi
export PATH=$doctor_path

if workspace_present; then
  printf 'The existing workspace is intact; init is not needed.\n'
else
  printf 'Creating or repairing the workspace without replacing existing files...\n'
  "$APPARATUS_BIN" init "$target" || fail "The workspace could not be created or repaired."
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
if ! /usr/bin/grep -Eq '^uv: ".+"$' "$report"; then
  fail "Doctor did not confirm the installed user-scope toolchain."
fi
if ! /usr/bin/grep -q '^  at_risk: false$' "$report"; then
  fail "Doctor reported that the workspace is inside a sync engine."
fi
if [[ -z $git_path ]]; then
  [[ $doctor_status -eq 1 ]] || [[ $doctor_status -eq 0 ]] || \
    fail "Doctor could not complete the workspace check."
  /usr/bin/grep -q '^git: null$' "$report" && \
    /usr/bin/grep -q '^snapshots: "unavailable"$' "$report" || \
    fail "Doctor did not record the expected git-absent snapshot state."
else
  [[ $doctor_status -eq 0 ]] || fail "Doctor found a blocked or incomplete toolchain."
  /usr/bin/grep -Eq '^git: ".+"$' "$report" && \
    /usr/bin/grep -q '^snapshots: "available"$' "$report" || \
    fail "Doctor did not confirm the expected snapshot state."
fi

printf 'Apparatus is ready at %s. Open Welcome.md with your AI app to begin.\n' "$target"
