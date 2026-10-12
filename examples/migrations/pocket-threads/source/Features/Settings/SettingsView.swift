import SwiftUI

struct SettingsView: View {
    var body: some View {
        List {
            Button("Notifications") { Router.shared.navigate(to: .settings(.notifications)) }
            Button("About") { Router.shared.navigate(to: .settings(.about)) }
        }
    }
}
