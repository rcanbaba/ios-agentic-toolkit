import Foundation

@MainActor
final class ThreadListViewModel: ObservableObject {
    @Published var threads: [Thread] = []

    func load() async {
        threads = (try? await APIClient.shared.fetchThreads()) ?? []
        SocketClient.shared.onMessage = { [weak self] type, payload in
            if type == .threadUpdated { Task { await self?.load() } }
        }
    }

    func open(_ thread: Thread) {
        Router.shared.navigate(to: .thread(id: thread.id))
    }
}
