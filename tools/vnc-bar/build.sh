#!/usr/bin/env bash
# Build VNCBar.app (release), sign it, and with --install copy it to ~/Applications and launch it.
#
# Usage: tools/vnc-bar/build.sh [--install]
# Signing identity: $CODESIGN_IDENTITY (name or SHA-1), else the first valid "Apple Development" identity in the
# keychain, else ad-hoc. Ad-hoc signatures change on every build, which resets the Accessibility
# permission and makes the Keychain ask again, so a real identity is strongly preferred.
set -euo pipefail
cd "$(dirname "$0")"

swift build -c release
BIN="$(swift build -c release --show-bin-path)/VNCBar"

APP=build/VNCBar.app
rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS"
cp "$BIN" "$APP/Contents/MacOS/VNCBar"

# App icon, drawn by Icon/make-icon.swift; regenerated only when the script changes.
ICNS=build/AppIcon.icns
if [[ ! -f $ICNS || Icon/make-icon.swift -nt $ICNS ]]; then
    ICONSET=build/AppIcon.iconset
    rm -rf "$ICONSET" && mkdir -p "$ICONSET"
    swift Icon/make-icon.swift build/icon-1024.png
    for size in 16 32 128 256 512; do
        sips -z $size $size build/icon-1024.png --out "$ICONSET/icon_${size}x${size}.png" >/dev/null
        sips -z $((size * 2)) $((size * 2)) build/icon-1024.png --out "$ICONSET/icon_${size}x${size}@2x.png" >/dev/null
    done
    iconutil -c icns "$ICONSET" -o "$ICNS"
fi
mkdir -p "$APP/Contents/Resources"
cp "$ICNS" "$APP/Contents/Resources/AppIcon.icns"
cat > "$APP/Contents/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleIdentifier</key><string>io.github.rcanbaba.VNCBar</string>
    <key>CFBundleName</key><string>VNCBar</string>
    <key>CFBundleExecutable</key><string>VNCBar</string>
    <key>CFBundlePackageType</key><string>APPL</string>
    <key>CFBundleIconFile</key><string>AppIcon</string>
    <key>CFBundleShortVersionString</key><string>0.1.0</string>
    <key>CFBundleVersion</key><string>1</string>
    <key>LSMinimumSystemVersion</key><string>14.0</string>
    <key>LSUIElement</key><true/>
    <key>CFBundleURLTypes</key>
    <array>
        <dict>
            <key>CFBundleURLName</key><string>io.github.rcanbaba.VNCBar</string>
            <key>CFBundleURLSchemes</key><array><string>vncbar</string></array>
        </dict>
    </array>
</dict>
</plist>
PLIST

# By SHA-1 hash: several certificates often share one "Apple Development: <name>" label.
IDENTITY=${CODESIGN_IDENTITY:-$(security find-identity -v -p codesigning \
    | awk '/"Apple Development/ {print $2; exit}')}
if [[ -z $IDENTITY ]]; then
    echo "warning: no Apple Development identity; signing ad-hoc (Accessibility must be re-granted after every build)" >&2
    IDENTITY=-
fi
codesign --force --sign "$IDENTITY" "$APP"
echo "built $APP"

if [[ ${1:-} == "--install" ]]; then
    pkill -x VNCBar || true
    rm -rf ~/Applications/VNCBar.app
    mkdir -p ~/Applications
    ditto "$APP" ~/Applications/VNCBar.app
    open ~/Applications/VNCBar.app
    echo "installed ~/Applications/VNCBar.app"
fi
