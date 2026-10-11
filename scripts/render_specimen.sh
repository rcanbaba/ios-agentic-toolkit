#!/usr/bin/env bash
# Render the generated design-system specimen to PNG files on an iOS Simulator.
#
# Deterministic visual feedback for the design-system workflow: the agent (and
# the human) can look at exactly what the generated SwiftUI code draws.
#
# Usage: render_specimen.sh <generated-dir> <out-dir> [--fonts <dir>]
#   <generated-dir>  contains DesignTokens.swift and DesignSystemSpecimen.swift
#   <out-dir>        receives specimen-light.png, specimen-dark.png, specimen-large-type.png
#   --fonts <dir>    .ttf/.otf files to bundle and register (for bundled families)
#
# Uses an already booted iPhone simulator, or boots one and shuts it down after.
# Needs Xcode command line tools. No Xcode project is created.
set -euo pipefail

usage() { echo "usage: render_specimen.sh <generated-dir> <out-dir> [--fonts <dir>]" >&2; exit 2; }
[[ $# -ge 2 ]] || usage
GEN_DIR=$(cd "$1" && pwd)
OUT_DIR=$2
FONTS_DIR=""
if [[ $# -ge 4 && $3 == "--fonts" ]]; then FONTS_DIR=$(cd "$4" && pwd); fi
[[ -f "$GEN_DIR/DesignTokens.swift" && -f "$GEN_DIR/DesignSystemSpecimen.swift" ]] || { echo "error: generated files not found in $GEN_DIR" >&2; exit 2; }
mkdir -p "$OUT_DIR"
OUT_DIR=$(cd "$OUT_DIR" && pwd)

BUNDLE_ID="dev.ios-agentic-toolkit.specimen-renderer"
WORK=$(mktemp -d)
APP="$WORK/SpecimenRenderer.app"
mkdir -p "$APP"
trap 'rm -rf "${WORK:?}"' EXIT

cat > "$WORK/main.swift" <<'SWIFT'
import SwiftUI

@main
struct SpecimenRendererApp: App {
    var body: some Scene {
        WindowGroup {
            Text("Rendering specimen…").task { await render() }
        }
    }
}

@MainActor
func render() async {
    let dir = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0]
    // Large type renders a much taller image; @1x keeps it within ImageRenderer limits.
    let variants: [(String, ColorScheme, DynamicTypeSize, CGFloat)] = [
        ("light", .light, .large, 2),
        ("dark", .dark, .large, 2),
        ("large-type", .light, .accessibility2, 1),
    ]
    for (name, scheme, typeSize, scale) in variants {
        let view = DesignSystemSpecimenContent()
            .frame(width: 393)
            .environment(\.colorScheme, scheme)
            .environment(\.dynamicTypeSize, typeSize)
        let renderer = ImageRenderer(content: view)
        renderer.scale = scale
        if let data = renderer.uiImage?.pngData() {
            try? data.write(to: dir.appendingPathComponent("specimen-\(name).png"))
        } else {
            try? Data().write(to: dir.appendingPathComponent("failed-\(name)"))
        }
    }
    try? Data().write(to: dir.appendingPathComponent("done"))
}
SWIFT

FONT_PLIST=""
if [[ -n "$FONTS_DIR" ]]; then
    FONT_PLIST="<key>UIAppFonts</key><array>"
    for f in "$FONTS_DIR"/*.ttf "$FONTS_DIR"/*.otf; do
        [[ -e "$f" ]] || continue
        cp "$f" "$APP/"
        FONT_PLIST+="<string>$(basename "$f")</string>"
    done
    FONT_PLIST+="</array>"
fi

cat > "$APP/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
<key>CFBundleIdentifier</key><string>$BUNDLE_ID</string>
<key>CFBundleExecutable</key><string>SpecimenRenderer</string>
<key>CFBundleName</key><string>SpecimenRenderer</string>
<key>CFBundlePackageType</key><string>APPL</string>
<key>CFBundleVersion</key><string>1</string>
<key>CFBundleShortVersionString</key><string>1.0</string>
<key>MinimumOSVersion</key><string>17.0</string>
<key>UIDeviceFamily</key><array><integer>1</integer></array>
<key>UILaunchScreen</key><dict/>
$FONT_PLIST
</dict></plist>
PLIST

echo "compiling renderer…"
xcrun --sdk iphonesimulator swiftc -parse-as-library -O \
    -target arm64-apple-ios17.0-simulator \
    "$WORK/main.swift" "$GEN_DIR/DesignTokens.swift" "$GEN_DIR/DesignSystemSpecimen.swift" \
    -o "$APP/SpecimenRenderer"
codesign --force --sign - "$APP" >/dev/null 2>&1 || true

DEVICE=$(xcrun simctl list devices booted | grep -E "iPhone" | head -1 | grep -oE '[0-9A-F-]{36}' || true)
BOOTED_BY_US=0
if [[ -z "$DEVICE" ]]; then
    DEVICE=$(xcrun simctl list devices available | grep -E "iPhone" | head -1 | grep -oE '[0-9A-F-]{36}')
    echo "booting simulator $DEVICE…"
    xcrun simctl boot "$DEVICE"
    BOOTED_BY_US=1
fi

xcrun simctl uninstall "$DEVICE" "$BUNDLE_ID" >/dev/null 2>&1 || true
xcrun simctl install "$DEVICE" "$APP"
DATA=$(xcrun simctl get_app_container "$DEVICE" "$BUNDLE_ID" data)
rm -f "${DATA:?}/Documents/done" "${DATA:?}"/Documents/failed-*
xcrun simctl launch "$DEVICE" "$BUNDLE_ID" >/dev/null

for _ in $(seq 1 60); do
    [[ -f "$DATA/Documents/done" ]] && break
    sleep 0.5
done
[[ -f "$DATA/Documents/done" ]] || { echo "error: renderer did not finish within 30s" >&2; exit 1; }

cp "$DATA"/Documents/specimen-*.png "$OUT_DIR/"
for f in "$DATA"/Documents/failed-*; do
    [[ -e "$f" ]] && echo "warning: could not render $(basename "$f" | sed 's/^failed-//') variant" >&2
done
xcrun simctl terminate "$DEVICE" "$BUNDLE_ID" >/dev/null 2>&1 || true
xcrun simctl uninstall "$DEVICE" "$BUNDLE_ID" >/dev/null 2>&1 || true
[[ $BOOTED_BY_US -eq 1 ]] && xcrun simctl shutdown "$DEVICE" >/dev/null 2>&1 || true

ls -1 "$OUT_DIR"/specimen-*.png
