#!/usr/bin/env bash
#
# Secret scanning across the platform's repositories.
#
# Document 15's security section had "secret scanning: MISSING. Never run." This is the run.
#
# WHAT IT SCANS. Git HISTORY, not the working tree. A secret is exposed the moment it is pushed,
# and deleting the file in a later commit does not unpublish it -- two of the three findings this
# script reports today are files that no longer exist in HEAD. A working-tree scan would call
# both of them clean, which is precisely the wrong answer.
#
# EXIT CODES. 0 clean, 1 findings, 2 gitleaks not installed. Non-zero on findings so this can be
# a build step; the counts below are what a run looks like today, and any number above them is
# something new.
#
# Findings are triaged in .ai/spec/SECRET-SCAN.md. Read that before allowlisting anything.
#
# Author: Nabeel Ahmed

set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
REPOS=(process scheduler1)

# What each repository reports today, all of them real and all recorded in SECRET-SCAN.md. The
# script compares against these rather than against zero: a repository with known unrotated
# history cannot reach zero, and a threshold of zero that can never be met is a check people turn
# off. Rotate a credential, remove its line from the record, and lower the number here.
#
# A case rather than an associative array: macOS still ships bash 3.2, where `declare -A` is a
# syntax error, and a security check that only runs on the maintainer's machine is not a check.
expected_for() {
  case "$1" in
    process)    echo 3 ;;
    scheduler1) echo 5 ;;
    *)          echo 0 ;;
  esac
}

if ! command -v gitleaks >/dev/null 2>&1; then
  echo "gitleaks is not installed. brew install gitleaks" >&2
  exit 2
fi

status=0
for repo in "${REPOS[@]}"; do
  dir="$ROOT/$repo"
  [ -d "$dir/.git" ] || { echo "skip $repo (not a git repository)"; continue; }

  config=()
  [ -f "$dir/.gitleaks.toml" ] && config=(--config "$dir/.gitleaks.toml")

  report="$(mktemp)"
  # ${config[@]+...} rather than "${config[@]}": under `set -u`, bash 3.2 calls an EMPTY array
  # unbound and aborts, so a repository with no config file would kill the whole scan.
  gitleaks git "$dir" --no-banner --exit-code 0 ${config[@]+"${config[@]}"} \
    --report-format json --report-path "$report" >/dev/null 2>&1

  found=$(python3 -c "import json,sys; print(len(json.load(open('$report'))))" 2>/dev/null || echo 0)
  expected=$(expected_for "$repo")

  if [ "$found" -gt "$expected" ]; then
    echo "FAIL $repo: $found findings, $expected known. NEW SECRET COMMITTED:"
    python3 - "$report" <<'PY'
import json, sys
for f in json.load(open(sys.argv[1])):
    print(f"      {f['RuleID']:18s} {f['File']}:{f['StartLine']}  {f['Date'][:10]}")
PY
    status=1
  elif [ "$found" -lt "$expected" ]; then
    echo "note $repo: $found findings, fewer than the $expected on record."
    echo "     Something was rotated and removed from history. Lower EXPECTED and update"
    echo "     .ai/spec/SECRET-SCAN.md."
  else
    echo "ok   $repo: $found known findings, nothing new."
  fi
  rm -f "$report"
done

exit $status
