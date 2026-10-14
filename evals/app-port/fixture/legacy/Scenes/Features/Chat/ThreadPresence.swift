import Foundation

// Declares an unrelated `isOnline`; only the `extension User` file may satisfy `User.isOnline`.
struct ThreadPresence {
    var isOnline: Bool
}
