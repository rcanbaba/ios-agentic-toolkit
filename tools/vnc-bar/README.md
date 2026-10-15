# VNCBar

One-click Screen Sharing connections to remote Macs, including the remote
login screen. Design, usage and security model:
[docs/tools/vnc-bar.md](../../docs/tools/vnc-bar.md).

```sh
./build.sh --install        # build, sign, install to ~/Applications and launch
swift test                  # address parsing, URLs, key map, window matching
```

| Path | What |
|---|---|
| `Sources/VNCBar/` | The app: popover UI, server store, Keychain, connect flow, typing, hotkey, URL scheme |
| `Tests/VNCBarTests/` | Unit tests for the deterministic parts |
| `Icon/make-icon.swift` | Draws the app icon; `build.sh` turns it into `AppIcon.icns` |
| `build.sh` | Bundles `VNCBar.app`, signs it, installs it with `--install` |
