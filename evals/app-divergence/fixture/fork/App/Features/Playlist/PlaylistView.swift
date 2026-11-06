import SwiftUI

struct PlaylistView: View {
    @StateObject var viewModel: PlaylistViewModel
    let playlistId: String
    let level: Int

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            if let playlist = viewModel.playlist {
                Image("cover-default")
                    .resizable()
                    .frame(width: 120, height: 120)
                Text(playlist.name)
                    .font(.title2)
                Text("playlist.track_count \(playlist.trackCount)")
                    .foregroundStyle(.secondary)
                Image("level_\(level)")
                ForEach(playlist.tracks) { track in
                    Button(track.title) { viewModel.play(track) }
                }
            } else if viewModel.isLoading {
                ProgressView()
            }
        }
        .padding()
        .task { await viewModel.loadTracks(playlistId: playlistId) }
    }
}
