import Foundation

// Queue handling, moved verbatim from PlayerViewModel.swift.
extension PlayerViewModel {
    func enqueue(_ id: String) {
        queue.append(id)
        if current == nil { advance() }
    }

    func advance() {
        current = queue.isEmpty ? nil : queue.removeFirst()
    }

    func clear() {
        queue.removeAll()
        current = nil
    }
}
