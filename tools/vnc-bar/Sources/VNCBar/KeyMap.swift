import Carbon.HIToolbox
import CoreGraphics

/// Character → (key code, modifiers) on the current keyboard layout, found the way System Events'
/// `keystroke` does: by asking the layout what every key produces with no modifier, Shift, Option
/// and Shift+Option. Screen Sharing forwards key codes, so the remote Mac reads them with its own
/// layout; typing is correct when both Macs use the same layout.
struct KeyMap {
    struct Stroke: Equatable {
        let keyCode: CGKeyCode
        let shift: Bool
        let option: Bool
    }

    private(set) var strokes: [Character: Stroke] = [:]
    let layoutName: String

    /// Key codes that never produce text we want (keypad, so digits come from the main row).
    private static let skipped: Set<CGKeyCode> = Set(65...92)

    /// TIS asserts that it runs on the main thread.
    @MainActor
    init?() {
        guard let source = TISCopyCurrentKeyboardLayoutInputSource()?.takeRetainedValue()
                ?? TISCopyCurrentASCIICapableKeyboardLayoutInputSource()?.takeRetainedValue(),
              let rawData = TISGetInputSourceProperty(source, kTISPropertyUnicodeKeyLayoutData) else { return nil }
        let data = Unmanaged<CFData>.fromOpaque(rawData).takeUnretainedValue() as Data
        if let rawName = TISGetInputSourceProperty(source, kTISPropertyLocalizedName) {
            layoutName = Unmanaged<CFString>.fromOpaque(rawName).takeUnretainedValue() as String
        } else {
            layoutName = "current layout"
        }

        let keyboardType = UInt32(LMGetKbdType())
        // Fewer modifiers first, so "a" is never mapped to an Option combination.
        let modifierSets: [(shift: Bool, option: Bool)] = [(false, false), (true, false), (false, true), (true, true)]
        data.withUnsafeBytes { buffer in
            guard let layout = buffer.baseAddress?.assumingMemoryBound(to: UCKeyboardLayout.self) else { return }
            for mods in modifierSets {
                let state = UInt32(((mods.shift ? shiftKey : 0) | (mods.option ? optionKey : 0)) >> 8) & 0xFF
                for code in CGKeyCode(0)..<128 where !Self.skipped.contains(code) {
                    var deadKeyState: UInt32 = 0
                    var length = 0
                    var chars = [UniChar](repeating: 0, count: 4)
                    let status = UCKeyTranslate(layout, code, UInt16(kUCKeyActionDown), state, keyboardType,
                                                0, &deadKeyState, chars.count, &length, &chars)
                    // A dead key (an accent waiting for the next key) is never used for a character.
                    guard status == noErr, deadKeyState == 0, length > 0 else { continue }
                    let string = String(utf16CodeUnits: chars, count: length)
                    guard string.count == 1, let ch = string.first,
                          let scalar = ch.unicodeScalars.first, scalar.value >= 0x20, scalar.value != 0x7F,
                          strokes[ch] == nil else { continue }
                    strokes[ch] = Stroke(keyCode: code, shift: mods.shift, option: mods.option)
                }
            }
        }
    }

    /// Positions (1-based) of characters the layout cannot produce; never the characters themselves.
    func unmappable(_ text: String) -> [Int] {
        text.enumerated().compactMap { strokes[$0.element] == nil ? $0.offset + 1 : nil }
    }
}
