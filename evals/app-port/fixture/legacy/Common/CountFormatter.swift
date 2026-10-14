import Foundation

enum CountFormatter {
    static func short(_ value: Int) -> String {
        value >= 1_000 ? "\(value / 1_000)K" : "\(value)"
    }
}
