import Foundation

/// User settings in UserDefaults. Keys are shared with the SwiftUI settings view (@AppStorage).
enum Settings {
    static let autoTypeKey = "autoType"
    static let autoStandardKey = "autoChooseStandard"
    static let loginDelayKey = "loginDelaySeconds"
    static let keyDelayKey = "keyDelayMilliseconds"

    private static var defaults: UserDefaults { .standard }

    static var autoType: Bool { defaults.object(forKey: autoTypeKey) as? Bool ?? true }
    static var autoChooseStandard: Bool { defaults.object(forKey: autoStandardKey) as? Bool ?? true }
    static var loginDelay: Duration {
        .milliseconds(Int((defaults.object(forKey: loginDelayKey) as? Double ?? 3) * 1000))
    }
    static var keyDelay: Duration {
        .milliseconds(max(10, defaults.object(forKey: keyDelayKey) as? Int ?? 100))
    }
}
