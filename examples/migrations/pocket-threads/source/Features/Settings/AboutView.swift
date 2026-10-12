import SwiftUI

struct AboutView: View {
    var body: some View { Text("Version \(Bundle.main.infoDictionary?["CFBundleShortVersionString"] ?? "")") }
}
