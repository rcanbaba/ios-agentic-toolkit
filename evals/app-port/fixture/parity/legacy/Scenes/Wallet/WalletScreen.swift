import SwiftUI

struct WalletScreen: View {
    var body: some View {
        Button("wallet_title".localized) {
            Task { try? await APIClient.shared.buyTokens(productId: "p1") }
        }
        .onAppear { _ = Route.wallet }
    }
}
