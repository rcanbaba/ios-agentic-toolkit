import AppKit
import Carbon.HIToolbox

/// A global hotkey through Carbon's RegisterEventHotKey (no Accessibility needed to receive it).
@MainActor
final class HotKey {
    private static var action: (() -> Void)?
    private var ref: EventHotKeyRef?

    /// `keyCode` is a key position (kVK_ANSI_P is the P key on Latin layouts, Turkish Q included).
    init(keyCode: Int, modifiers: Int, action: @escaping () -> Void) {
        HotKey.action = action
        var spec = EventTypeSpec(eventClass: OSType(kEventClassKeyboard), eventKind: UInt32(kEventHotKeyPressed))
        InstallEventHandler(GetApplicationEventTarget(), { _, _, _ in
            MainActor.assumeIsolated { HotKey.action?() }
            return noErr
        }, 1, &spec, nil, nil)
        let id = EventHotKeyID(signature: OSType(0x564E_4342), id: 1)  // "VNCB"
        RegisterEventHotKey(UInt32(keyCode), UInt32(modifiers), id, GetApplicationEventTarget(), 0, &ref)
    }
}
