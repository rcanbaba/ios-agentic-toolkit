#!/usr/bin/env bash
# Replay the migration pipeline on examples/migrations/pocket-threads from the parts as
# the area agents authored them, and compare with the checked-in outputs.
#
# Usage: evals/feature-inventory/replay.sh [--update]
#   (no flag)  replay in a temporary copy twice: the first run must reproduce the
#              checked-in example exactly, the second must change nothing
#   --update   replay in place, to regenerate the example after an intended change
# Exit code 0 = identical, 1 = differences or an unexpected step exit code.
set -euo pipefail

TOOLKIT=$(cd "$(dirname "$0")/../.." && pwd)
EXAMPLE="$TOOLKIT/examples/migrations/pocket-threads"
S="$TOOLKIT/scripts"

if [[ ${1:-} == "--update" ]]; then
    WORK="$EXAMPLE"
else
    TMP=$(mktemp -d)
    trap 'rm -rf "${TMP:?}"' EXIT
    cp -R "$EXAMPLE" "$TMP/"
    WORK="$TMP/pocket-threads"
fi
M="$WORK/migration"

# Reset to the agents' raw output.
rm -rf "${M:?}/inventory/parts"
cp -R "$M/inventory/parts.as-authored" "$M/inventory/parts"
rm -f "$M/inventory/reconciliation.json" "$M/verification/applied.json"

step() {  # step <expected exit code> <script> <args...>
    local expected=$1 script=$2 code=0
    shift 2
    python3 "$S/$script" "$@" >/dev/null || code=$?
    if [[ $code -ne $expected ]]; then
        echo "FAIL: $script exited $code, expected $expected" >&2
        python3 "$S/$script" "$@" >&2 || true
        exit 1
    fi
}

pipeline() {
    step 0 extract_enumerations.py "$M/enumerations.config.json" --out "$M/inventory/enumerations.json"
    step "$1" merge_inventory.py --migration-dir "$M"   # raw parts have known problems on the first run
    step 0 reconcile_inventory.py --migration-dir "$M" --overrides "$M/reconcile.overrides.json"
    step 0 merge_inventory.py --migration-dir "$M"
    step 0 apply_verification.py --migration-dir "$M"
    step 0 reconcile_inventory.py --migration-dir "$M" --overrides "$M/reconcile.overrides.json"
    step 0 merge_inventory.py --migration-dir "$M"
    step 0 render_inventory.py --migration-dir "$M" --title "Pocket Threads feature inventory"
    step 0 validate_flow_spec.py "$M"/flow-specs/*.json --migration-dir "$M" --require-decisions
    step 0 render_flow_spec.py "$M"/flow-specs/*.json
    step 0 render_pending.py "$M/PENDING_DECISIONS.md" "$M"/flow-specs/*.json
    step 0 merge_inventory.py --migration-dir "$M" --coverage-only
}

pipeline 1
if [[ ${1:-} == "--update" ]]; then
    echo "example regenerated: $EXAMPLE"
    exit 0
fi
diff -r -x '__pycache__' "$EXAMPLE" "$WORK" || { echo "FAIL: replay differs from the checked-in example" >&2; exit 1; }
pipeline 0
diff -r -x '__pycache__' "$EXAMPLE" "$WORK" || { echo "FAIL: a second run changed the outputs" >&2; exit 1; }
echo "OK: replay reproduces the example exactly, and a second run changes nothing"
