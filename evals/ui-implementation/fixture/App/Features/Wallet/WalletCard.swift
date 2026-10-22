import SwiftUI

// A card written without the design system.
struct WalletCard: View {
    let balance: String

    var body: some View {
        VStack(alignment: .leading) {
            Text("Balance").font(.headline)
            Text(balance)
                .font(.system(size: 28, weight: .bold))
                .foregroundStyle(.blue)
            Text("Top up").dsFont(.huge)
        }
        .padding(DS.Spacing.md)
        .background(Color(red: 0.98, green: 0.95, blue: 0.9))
        .overlay(RoundedRectangle(cornerRadius: 14).stroke(DS.Colors.brandPink))
        // .font(.system(size: 12)) in a comment is ignored
    }
}
