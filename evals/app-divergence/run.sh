#!/usr/bin/env bash
# Run the divergence scripts on the synthetic fixture and compare their reports with the expected ones.
#
# Usage: evals/app-divergence/run.sh [--update]
#   (no flag)  run in a temporary copy; the reports must reproduce expected/ exactly
#   --update   rewrite expected/ from a fresh run after an intended change
# Exit code 0 = identical, 1 = differences or an unexpected exit code.
set -euo pipefail

TOOLKIT=$(cd "$(dirname "$0")/../.." && pwd)
EVAL="$TOOLKIT/evals/app-divergence"
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
        echo "FAIL: $script $report exited $code, expected $expected" >&2
        exit 1
    fi
}

cp -R fork baseline  # the copy taken before the rename

# Refused maps write nothing.
run 1 rename-conflict.json rename_identifiers.py renames/02-conflict.json --src fork/App
run 1 rename-refused.json rename_identifiers.py renames/03-refused.json --src fork/App
if ! diff -r fork baseline >/dev/null; then
    echo "FAIL: a refused rename wrote files" >&2
    exit 1
fi

# The rename, then the file and folder moves a person makes to match it.
run 0 rename.json rename_identifiers.py renames/01-mixtape.json --src fork/App
(
    cd fork/App
    mv Features/Playlist Features/Mixtape
    mv Features/Mixtape/PlaylistView.swift Features/Mixtape/MixtapeView.swift
    mv Features/Mixtape/PlaylistViewModel.swift Features/Mixtape/MixtapeViewModel.swift
    mv Features/Mixtape/PlaylistCell.swift Features/Mixtape/MixtapeCell.swift
    mv Core/Models/Playlist.swift Core/Models/Mixtape.swift
)
run 0 verify.json verify_rename.py renames/01-mixtape.json --src fork/App --baseline baseline/App

# A copy where a "rename" also edited a string, added a line and changed an unmapped name.
cp -R fork tampered
sed -i.bak 's/\[playlist\] load failed/[mixtape] load failed/' tampered/App/Features/Mixtape/MixtapeViewModel.swift
sed -i.bak 's/let rest = seconds % 60/let remainder = seconds % 60/' tampered/App/Core/Utility/Formatters.swift
printf '\n// added\n' >> tampered/App/App/SceneDelegate.swift
rm tampered/App/Features/Mixtape/*.bak tampered/App/Core/Utility/*.bak
run 1 verify-tampered.json verify_rename.py renames/01-mixtape.json --src tampered/App --baseline baseline/App

# What the compiler does not check, before and after the rename.
bindings=(--asset-literals '^eq_[a-z]+$')
run 1 bindings-before.json find_string_bindings.py --src baseline/App --catalog baseline/App/Resources/Assets.xcassets "${bindings[@]}"
run 1 bindings-after.json find_string_bindings.py --src fork/App --catalog fork/App/Resources/Assets.xcassets "${bindings[@]}"

run 0 similarity.json similarity.py --original original/App --fork fork/App --renames renames/01-mixtape.json \
    --md "$OUT/similarity.md"

run 0 split-good.json check_split.py --baseline split/baseline/PlayerViewModel.swift \
    --parts split/good/PlayerViewModel.swift split/good/PlayerViewModel+Queue.swift
run 1 split-bad.json check_split.py --baseline split/baseline/PlayerViewModel.swift \
    --parts split/bad/PlayerViewModel.swift split/bad/PlayerViewModel+Queue.swift

if [[ ${1:-} == "--update" ]]; then
    rm -rf "$EVAL/expected"
    cp -R "$OUT" "$EVAL/expected"
    echo "expected/ updated"
    exit 0
fi

if diff -ru "$EVAL/expected" "$OUT"; then
    echo "OK: divergence scripts reproduce expected/"
else
    exit 1
fi
