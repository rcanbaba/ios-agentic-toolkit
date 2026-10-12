import Foundation

enum RelativeDateFormatter {
    static func string(from date: Date) -> String {
        RelativeDateTimeFormatter().localizedString(for: date, relativeTo: Date())
    }
}
