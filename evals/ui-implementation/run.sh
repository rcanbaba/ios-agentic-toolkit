#!/usr/bin/env bash
# Run check_ds_usage.py on the synthetic fixture and compare its report with the expected one.
#
# Usage: evals/ui-implementation/run.sh [--update]
#   --update   rewrite expected/ after an intended change
# Exit code 0 = identical, 1 = differences or an unexpected exit code.
set -euo pipefail

TOOLKIT=$(cd "$(dirname "$0")/../.." && pwd)
EVAL="$TOOLKIT/evals/ui-implementation"
TMP=$(mktemp -d)
trap 'rm -rf "${TMP:?}"' EXIT
cd "$EVAL/fixture"

code=0
python3 "$TOOLKIT/scripts/check_ds_usage.py" App/DesignSystem/design-system.json App \
    --exclude 'App/DesignSystem/Generated/*' --out "$TMP/ds-usage.json" >/dev/null || code=$?
if [[ $code -ne 1 ]]; then
    echo "FAIL: check_ds_usage.py exited $code, expected 1" >&2
    exit 1
fi

if [[ ${1:-} == "--update" ]]; then
    mkdir -p "$EVAL/expected"
    cp "$TMP/ds-usage.json" "$EVAL/expected/"
    echo "expected/ updated"
    exit 0
fi

diff -u "$EVAL/expected/ds-usage.json" "$TMP/ds-usage.json" && echo "OK: check_ds_usage.py reproduces expected/"
