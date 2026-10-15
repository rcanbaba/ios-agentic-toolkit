import SwiftUI

// Ported, then restyled; behavior kept.
struct ProfileScreen: View {
    @Binding var path: [Route]

    var body: some View {
        Button("profile_title".localized) { path.append(.gifts) }
            .buttonStyle(.borderedProminent)
            .task { try? await APIClient.shared.fetchProfile() }
    }
}
