import Foundation

@MainActor
final class PlaylistViewModel: ObservableObject {
    enum Source { case playlist, search }

    @Published private(set) var playlist: Playlist?
    @Published private(set) var isLoading = false
    let source: Source
    private let api: PlaylistAPI

    init(api: PlaylistAPI, source: Source) {
        self.api = api
        self.source = source
    }

    var screenName: String { "screen_" + String(describing: source) }

    func loadTracks(playlistId: String) async {
        isLoading = true
        defer { isLoading = false }
        do {
            playlist = try await api.fetchPlaylist(id: playlistId)
        } catch {
            print("[playlist] load failed: \(error.localizedDescription)")
        }
    }

    func play(_ track: Track) {
        print("play \(track.title)")
    }

    func shuffle() {
        guard let tracks = playlist?.tracks, let first = tracks.shuffled().first else { return }
        play(first)
    }
}

protocol PlaylistAPI {
    func fetchPlaylist(id: String) async throws -> Playlist
}
