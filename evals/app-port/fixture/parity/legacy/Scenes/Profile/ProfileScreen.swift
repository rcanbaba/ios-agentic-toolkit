import SwiftUI

struct ProfileScreen: View {
    @Binding var path: [Route]

    var body: some View {
        Button("profile_title".localized) { path.append(.gifts) }
            .task { try? await APIClient.shared.fetchProfile() }
    }
}
