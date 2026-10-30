import Foundation
import os

extension PlayerViewModel {
    func enqueue(_ id: String) {
        queue.append(id)
        if current == nil { advance() }
    }

    func advance() {
        current = queue.isEmpty ? nil : queue.removeFirst()
    }
}

extension Logger {
    static let player = Logger()
}
