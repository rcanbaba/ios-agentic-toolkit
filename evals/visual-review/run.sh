#!/usr/bin/env bash
# Run the visual-review scripts on the synthetic fixture and compare with expected/.
#
# Usage: evals/visual-review/run.sh [--update]
#   (no flag)  lint, palette and the rendered review must reproduce expected/ exactly, and every
#              negative case must be rejected with its error
#   --update   rewrite expected/ after an intended change
# Needs Xcode command line tools (sample_colors.swift). Exit code 0 = pass, 1 = fail.
set -euo pipefail

TOOLKIT=$(cd "$(dirname "$0")/../.." && pwd)
EVAL="$TOOLKIT/evals/visual-review"
S="$TOOLKIT/scripts"
TMP=$(mktemp -d)
trap 'rm -rf "${TMP:?}"' EXIT
cp -R "$EVAL/fixture" "$TMP/"
cd "$TMP/fixture"
mkdir -p reports

expect() {  # expect <exit code> <command...>
    local expected=$1 code=0
    shift
    "$@" >/dev/null 2>&1 || code=$?
    if [[ $code -ne $expected ]]; then
        echo "FAIL: $* exited $code, expected $expected" >&2
        exit 1
    fi
}

expect 1 python3 "$S/check_ds_usage.py" design-system.json App --out reports/ds-usage.json
swift "$S/sample_colors.swift" screenshots/*.png > reports/samples.json
expect 1 python3 "$S/palette_check.py" design-system.json reports/samples.json --out reports/palette.json
expect 0 python3 "$S/validate_visual_review.py" review.json --md reports/review.md
rm reports/samples.json

if [[ ${1:-} == "--update" ]]; then
    rm -rf "$EVAL/expected"
    cp -R reports "$EVAL/expected"
    echo "expected/ updated"
    exit 0
fi

status=0
diff -ru "$EVAL/expected" reports || status=1
python3 "$EVAL/negative_cases.py" review.json "$S/validate_visual_review.py" || status=1
[[ $status -eq 0 ]] && echo "OK: visual-review scripts reproduce expected/ and reject every negative case"
exit $status
