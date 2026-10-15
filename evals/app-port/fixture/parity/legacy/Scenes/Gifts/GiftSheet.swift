import SwiftUI

struct GiftSheet: View {
    var body: some View {
        VStack {
            GiftCombo()
            Button("send") {
                Task {
                    try? await APIClient.shared.sendGift(id: 1)
                    Toast.show("gift_sent".localized)
                }
            }
        }
    }
}
