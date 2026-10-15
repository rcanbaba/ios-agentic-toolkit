import SwiftUI

struct PopoverView: View {
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("VNCBar").font(.headline)
            Text("No servers yet.")
                .foregroundStyle(.secondary)
                .frame(maxWidth: .infinity, minHeight: 80)
            Divider()
            HStack {
                Spacer()
                Button("Quit") { NSApplication.shared.terminate(nil) }
            }
        }
        .padding()
        .frame(width: 340)
    }
}
