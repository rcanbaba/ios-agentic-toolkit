import SwiftUI

// Clean: tokens only. The symbol size is not text, so the literal size is fine.
struct ProfileHeaderView: View {
    let name: String
    let followers: Int

    var body: some View {
        VStack(alignment: .leading, spacing: DS.Spacing.xs) {
            Text(name).dsFont(.display)
            HStack(spacing: DS.Spacing.xxs) {
                Image(systemName: "person.2.fill")
                    .font(.system(size: 14, weight: .semibold))
                    .foregroundStyle(DS.Colors.inkMuted)
                Text("\(followers)").dsFont(.label)
            }
            Button("Follow") {}
                .buttonStyle(DSPressableButtonStyle(component: DS.Components.primaryButton))
        }
        .padding(DS.Spacing.md)
        .background(DS.Gradients.paperFade)
        .background(DS.Gradients.dusk.opacity(0.1))
    }
}
