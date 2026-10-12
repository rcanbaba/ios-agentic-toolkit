import SwiftUI

struct ThreadListView: View {
    @StateObject var viewModel = ThreadListViewModel()

    var body: some View {
        List(viewModel.threads) { thread in
            Button(thread.title) { viewModel.open(thread) }
        }
        .task { await viewModel.load() }
        .overlay { if viewModel.threads.isEmpty { Text("No conversations yet") } }
    }
}
