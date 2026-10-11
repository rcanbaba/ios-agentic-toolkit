#!/usr/bin/env bash
# Render the generated design-system specimen to PNG files on an iOS Simulator.
#
# Deterministic visual feedback for the design-system workflow: the agent (and
# the human) can look at exactly what the generated SwiftUI code draws.
#
# Usage: render_specimen.sh <generated-dir> <out-dir> [--fonts <dir>]
#   <generated-dir>  contains DesignTokens.swift and DesignSystemSpecimen.swift
#   <out-dir>        receives specimen-light.png, specimen-dark.png, specimen-large-type.png;
#                    specimens taller than ~8000px are split into -1, -2, ... tiles
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

// ImageRenderer/CGContext fail above roughly 8192px per side; stay below that.
let maxPixels: CGFloat = 8000
let width: CGFloat = 393

@MainActor
func render() async {
    let dir = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0]
    let variants: [(String, ColorScheme, DynamicTypeSize, CGFloat)] = [
        ("light", .light, .large, 2),
        ("dark", .dark, .large, 2),
        ("large-type", .light, .accessibility2, 1),
    ]
    for (name, scheme, typeSize, scale) in variants {
        let content = DesignSystemSpecimenContent()
            .environment(\.colorScheme, scheme)
            .environment(\.dynamicTypeSize, typeSize)
        // Never force a height on the content: that changes its layout (truncated
        // text). Measure with the same renderer at a tiny scale; uiImage.size is in points.
        let natural = content.frame(width: width).fixedSize(horizontal: false, vertical: true)
        let probe = ImageRenderer(content: natural)
        probe.scale = 0.25
        guard let height = probe.uiImage?.size.height, height > 0 else {
            try? Data().write(to: dir.appendingPathComponent("failed-\(name)"))
            continue
        }
        let tileHeight = floor(maxPixels / scale)
        let tiles = max(1, Int(ceil(height / tileHeight)))
        for index in 0..<tiles {
            let top = CGFloat(index) * tileHeight
            let slice = AnyView(tiles == 1 ? AnyView(natural) : AnyView(natural
                .offset(y: -top)
                .frame(width: width, height: min(tileHeight, height - top), alignment: .top)
                .clipped()))
            let renderer = ImageRenderer(content: slice)
            renderer.scale = scale
            let file = tiles == 1 ? "specimen-\(name)" : "specimen-\(name)-\(index + 1)"
            if let data = renderer.uiImage?.pngData() {
                try? data.write(to: dir.appendingPathComponent("\(file).png"))
            } else {
                try? Data().write(to: dir.appendingPathComponent("failed-\(file)"))
            }
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

for f in "$DATA"/Documents/failed-*; do
    [[ -e "$f" ]] && echo "warning: could not render $(basename "$f" | sed 's/^failed-//')" >&2
done
rm -f "${OUT_DIR:?}"/specimen-*.png
cp "$DATA"/Documents/specimen-*.png "$OUT_DIR/" 2>/dev/null || true
xcrun simctl terminate "$DEVICE" "$BUNDLE_ID" >/dev/null 2>&1 || true
xcrun simctl uninstall "$DEVICE" "$BUNDLE_ID" >/dev/null 2>&1 || true
[[ $BOOTED_BY_US -eq 1 ]] && xcrun simctl shutdown "$DEVICE" >/dev/null 2>&1 || true

ls -1 "$OUT_DIR"/specimen-*.png 2>/dev/null || { echo "error: no specimen images were rendered" >&2; exit 1; }
