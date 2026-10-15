#!/usr/bin/env bash
# Run the port scripts on the synthetic fixture and compare their reports with the expected ones.
#
# Usage: evals/app-port/run.sh [--update]
#   (no flag)  run in a temporary copy twice: the first run must reproduce expected/ exactly,
#              the second (on the already-ported copy) must find nothing new to copy
#   --update   rewrite expected/ from a fresh run after an intended change
# Exit code 0 = identical, 1 = differences or an unexpected exit code.
set -euo pipefail

TOOLKIT=$(cd "$(dirname "$0")/../.." && pwd)
EVAL="$TOOLKIT/evals/app-port"
S="$TOOLKIT/scripts"
TMP=$(mktemp -d)
trap 'rm -rf "${TMP:?}"' EXIT
cp -R "$EVAL/fixture" "$TMP/"
cd "$TMP/fixture"
OUT="$TMP/out"
mkdir -p "$OUT"

run() {  # run <expected exit> <report> <script> <args...>
    local expected=$1 report=$2 script=$3 code=0
    shift 3
    python3 "$S/$script" "$@" --out "$OUT/$report" >/dev/null 2>&1 || code=$?
    if [[ $code -ne $expected ]]; then
        echo "FAIL: $script exited $code, expected $expected" >&2
        exit 1
    fi
}

symbols=(--legacy legacy --target target --errors build.log --path-map path-map.json --exclude "Assets.xcassets/*")
assets=(--legacy-catalog legacy/Assets.xcassets --target-src target --into target/App/Resources/Assets.xcassets/Legacy
        --errors build.log --scan)

run 1 symbols.json port_missing_symbols.py "${symbols[@]}" --apply
run 1 assets.json port_assets.py "${assets[@]}" --apply
run 1 styling.json find_legacy_styling.py migration/port/styling.config.json --batches 2
run 1 parity.json parity_check.py parity/parity.config.json
(cd target && find . -type f | LC_ALL=C sort) > "$OUT/target-files.txt"

if [[ ${1:-} == "--update" ]]; then
    rm -rf "$EVAL/expected"
    cp -R "$OUT" "$EVAL/expected"
    echo "expected/ updated"
    exit 0
fi

status=0
diff -ru "$EVAL/expected" "$OUT" || status=1

# Second run on the ported copy: nothing new may be planned or copied.
run 1 symbols-2.json port_missing_symbols.py "${symbols[@]}" --apply
run 1 assets-2.json port_assets.py "${assets[@]}" --apply
python3 - "$OUT" <<'PY' || status=1
import json, sys
out = sys.argv[1]
s = json.load(open(f"{out}/symbols-2.json"))
a = json.load(open(f"{out}/assets-2.json"))
problems = []
if s["plan"] or s["copied"]:
    problems.append(f"second symbol run planned {[p['legacy'] for p in s['plan']]}")
if a["plan"] or a["copied"]:
    problems.append(f"second asset run planned {[p['set'] for p in a['plan']]}")
for p in problems:
    print("FAIL:", p)
sys.exit(1 if problems else 0)
PY

[[ $status -eq 0 ]] && echo "OK: port scripts reproduce expected/ and are idempotent"
exit $status
