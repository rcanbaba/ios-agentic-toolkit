import AppKit
import CoreGraphics

/// Types text as key events (needs Accessibility only, no Apple Events), one character at a time,
/// with explicit Shift/Option down and up around each character, like System Events does.
@MainActor
struct Typer {
    static let returnKey: CGKeyCode = 36
    private static let shiftKey: CGKeyCode = 56
    private static let optionKey: CGKeyCode = 58

    struct Failure: LocalizedError {
        let message: String
        var errorDescription: String? { message }
    }

    let keyDelay: Duration

    /// Types `text`, then Return. `stillTarget` is checked before every key; when it turns false
    /// (the user switched apps) typing stops, so nothing is typed into the wrong window.
    func type(_ text: String, pressReturn: Bool, stillTarget: () -> Bool) async throws {
        guard let map = KeyMap() else { throw Failure(message: "Could not read the keyboard layout.") }
        let missing = map.unmappable(text)
        if !missing.isEmpty {
            throw Failure(message: "Characters at positions \(missing.map(String.init).joined(separator: ", ")) "
                          + "cannot be typed with the \(map.layoutName) layout.")
        }
        try await waitForModifiersReleased()
        let source = CGEventSource(stateID: .hidSystemState)

        for ch in text {
            guard stillTarget() else { throw Failure(message: "Stopped typing: Screen Sharing is no longer in front.") }
            let stroke = map.strokes[ch]!
            try await press(stroke.keyCode, shift: stroke.shift, option: stroke.option, source: source)
            try await Task.sleep(for: keyDelay)
        }
        if pressReturn {
            guard stillTarget() else { throw Failure(message: "Stopped typing: Screen Sharing is no longer in front.") }
            try await press(Self.returnKey, shift: false, option: false, source: source)
        }
    }

    private func press(_ code: CGKeyCode, shift: Bool, option: Bool, source: CGEventSource?) async throws {
        var flags: CGEventFlags = []
        if shift { flags.insert(.maskShift) }
        if option { flags.insert(.maskAlternate) }
        let modifiers = [(shift, Self.shiftKey), (option, Self.optionKey)].filter(\.0).map(\.1)

        for modifier in modifiers { post(modifier, down: true, flags: flags, source: source) }
        if !modifiers.isEmpty { try await Task.sleep(for: .milliseconds(10)) }
        post(code, down: true, flags: flags, source: source)
        post(code, down: false, flags: flags, source: source)
        if !modifiers.isEmpty { try await Task.sleep(for: .milliseconds(10)) }
        for modifier in modifiers.reversed() { post(modifier, down: false, flags: [], source: source) }
    }

    private func post(_ code: CGKeyCode, down: Bool, flags: CGEventFlags, source: CGEventSource?) {
        guard let event = CGEvent(keyboardEventSource: source, virtualKey: code, keyDown: down) else { return }
        event.flags = flags
        event.post(tap: .cghidEventTap)
    }

    /// A held ⌃/⌥/⌘/⇧ (for example from a hotkey) would combine with the typed keys.
    private func waitForModifiersReleased() async throws {
        let held: CGEventFlags = [.maskControl, .maskAlternate, .maskCommand, .maskShift]
        for _ in 0..<50 {
            if CGEventSource.flagsState(.combinedSessionState).intersection(held).isEmpty { return }
            try await Task.sleep(for: .milliseconds(100))
        }
        throw Failure(message: "Release the modifier keys, then try again.")
    }
}
