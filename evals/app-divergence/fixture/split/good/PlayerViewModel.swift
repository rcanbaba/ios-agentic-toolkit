import Foundation
import Combine

@MainActor
final class PlayerViewModel: ObservableObject {
    @Published private(set) var queue: [String] = []
    @Published private(set) var current: String?
    private var cancellables = Set<AnyCancellable>()

    init() {}

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
