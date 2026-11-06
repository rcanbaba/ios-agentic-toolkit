import Foundation

enum DurationText {
    static func minutesAndSeconds(_ seconds: Int) -> String {
        let minutes = seconds / 60
        let rest = seconds % 60
        return String(format: "%d:%02d", minutes, rest)
    }

    static func total(of tracks: [Track]) -> String {
        minutesAndSeconds(tracks.reduce(0) { $0 + $1.durationSeconds })
    }
}
