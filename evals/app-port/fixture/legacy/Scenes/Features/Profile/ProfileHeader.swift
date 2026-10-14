import SwiftUI

struct ProfileHeader: View {
    let user: User

    var body: some View {
        VStack {
            Text(user.displayHandle)
                .font(.Brand.title)
            Text(CountFormatter.short(user.followerCount))
        }
    }
}

extension User {
    var displayHandle: String { "@" + name }
}
