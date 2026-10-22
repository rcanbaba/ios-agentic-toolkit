import SwiftUI

// A list row with the defects a screenshot review found in a real port:
// a display-size number and a fixedSize that pushes the row past the screen width.
struct LeaderboardRowView: View {
    let rank: Int
    let name: String
    let points: Int

    var body: some View {
        HStack(spacing: 10) {
            Text("\(rank)").dsFont(.caption)
            Text(name).dsFont(.body).lineLimit(1)
            Spacer()
            Text("\(points)")
                .dsFont(.display)
                .fixedSize()
        }
        .padding(16)
        .padding(.vertical, 1) // ds-lint: allow literal-spacing hairline offset that matches the separator
    }
}
