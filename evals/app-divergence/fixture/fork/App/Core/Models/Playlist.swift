import Foundation

struct Track: Codable, Identifiable, Hashable {
    let id: String
    let title: String
    let durationSeconds: Int
}

struct Playlist: Codable, Identifiable {
    let id: String
    let playlistId: String
    let name: String
    let trackCount: Int
    var tracks: [Track]

    enum CodingKeys: String, CodingKey {
        case id
        case playlistId = "playlist_id"
        case name
        case trackCount = "track_count"
        case tracks
    }
}
