import Foundation
import Combine

@MainActor
final class PlayerViewModel: ObservableObject {
    @Published private(set) var queue: [String] = []
    @Published private(set) var current: String?
    private var cancellables = Set<AnyCancellable>()

    init() {}

    // MARK: - Queue

    func enqueue(_ id: String) {
        queue.append(id)
        if current == nil { advance() }
    }

    private func advance() {
        current = queue.isEmpty ? nil : queue.removeFirst()
    }

    func clear() {
        queue.removeAll()
        current = nil
    }

    // MARK: - Reporting

    func report(_ event: String) {
        print("[player] \(event)")
    }

    #if DEBUG
    func debugDump() {
        print("queue: \(queue)")
    }
    #endif
}
