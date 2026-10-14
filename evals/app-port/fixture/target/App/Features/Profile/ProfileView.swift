import SwiftUI

struct ProfileView: View {
    let user: User
    let tier: Tier

    var body: some View {
        VStack {
            ProfileHeader(user: user)
            Image(.follow)
            Image(._1XBoost)
            Image(.missingArt)
            Image(systemName: "star.fill")
            Color(.brandPrimary)
            Image("tab-home")
            Image(.chatSend)
            Image(.hero)
            Text(user.isOnline ? "online" : "")
            RowBadge()
        }
        .foregroundStyle(Color("textPrimary"))
    }
}
