#!/usr/bin/env bash
# Capture one app screen on an iOS Simulator in several appearance variants.
#
# Deterministic input for the visual-review workflow: the same screen in light, dark and large
# text, captured the same way every time. The app is relaunched for each variant with the given
# launch arguments (a debug flag or deep link that opens the screen), so trait changes are
# picked up from a clean start. The simulator's appearance and text size are restored afterwards.
#
# Usage: capture_screens.sh <udid> <bundle-id> <out-dir> <screen-name>
#                           [--variants light,dark,large-type] [--wait <seconds>] [-- <launch args>]
#   variants   any of light, dark, large-type (large-type = light at accessibility-extra-large)
#   --wait     seconds between launch and screenshot (default 4)
# Writes <out-dir>/<screen-name>-<variant>.png. Exit code 0 = all captured, 1 = a capture failed,
# 2 = usage error.
set -euo pipefail

usage() { echo "usage: capture_screens.sh <udid> <bundle-id> <out-dir> <screen-name> [--variants light,dark,large-type] [--wait N] [-- <launch args>]" >&2; exit 2; }
[[ $# -ge 4 ]] || usage
UDID=$1 BUNDLE=$2 OUT=$3 NAME=$4
shift 4
VARIANTS="light,dark,large-type"
WAIT=4
LAUNCH_ARGS=()
while [[ $# -gt 0 ]]; do
    case $1 in
        --variants) VARIANTS=$2; shift 2 ;;
        --wait) WAIT=$2; shift 2 ;;
        --) shift; LAUNCH_ARGS=("$@"); break ;;
        *) usage ;;
    esac
done
mkdir -p "$OUT"

ORIGINAL_APPEARANCE=$(xcrun simctl ui "$UDID" appearance)
ORIGINAL_SIZE=$(xcrun simctl ui "$UDID" content_size)
restore() {
    xcrun simctl ui "$UDID" appearance "$ORIGINAL_APPEARANCE" >/dev/null 2>&1 || true
    xcrun simctl ui "$UDID" content_size "$ORIGINAL_SIZE" >/dev/null 2>&1 || true
}
trap restore EXIT

status=0
IFS=',' read -ra LIST <<< "$VARIANTS"
for variant in "${LIST[@]}"; do
    case $variant in
        light) appearance=light; size=large ;;
        dark) appearance=dark; size=large ;;
        large-type) appearance=light; size=accessibility-extra-large ;;
        *) echo "unknown variant: $variant" >&2; exit 2 ;;
    esac
    xcrun simctl ui "$UDID" appearance "$appearance"
    xcrun simctl ui "$UDID" content_size "$size"
    xcrun simctl launch --terminate-running-process "$UDID" "$BUNDLE" ${LAUNCH_ARGS[@]+"${LAUNCH_ARGS[@]}"} >/dev/null
    sleep "$WAIT"
    file="$OUT/$NAME-$variant.png"
    if xcrun simctl io "$UDID" screenshot "$file" >/dev/null 2>&1; then
        echo "$file"
    else
        echo "error: could not capture $variant" >&2
        status=1
    fi
done
exit $status
