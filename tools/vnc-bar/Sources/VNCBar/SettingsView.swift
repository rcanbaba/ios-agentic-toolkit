import ServiceManagement
import SwiftUI

struct SettingsView: View {
    let done: () -> Void

    @AppStorage(Settings.autoTypeKey) private var autoType = true
    @AppStorage(Settings.autoStandardKey) private var autoStandard = true
    @AppStorage(Settings.loginDelayKey) private var loginDelay = 3.0
    @AppStorage(Settings.keyDelayKey) private var keyDelay = 100
    @State private var launchAtLogin = SMAppService.mainApp.status == .enabled
    @State private var error: String?

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Settings").font(.headline)
            VStack(alignment: .leading, spacing: 10) {
                Toggle("Type the password after connecting", isOn: $autoType)
                Toggle("Choose Standard in the connection-type dialog", isOn: $autoStandard)
                Toggle("Launch at login", isOn: $launchAtLogin)
                    .onChange(of: launchAtLogin) { _, on in setLaunchAtLogin(on) }
                Divider()
                Stepper(value: $loginDelay, in: 0...30, step: 0.5) {
                    Text("Login screen delay: \(loginDelay, format: .number.precision(.fractionLength(1))) s")
                }
                Stepper(value: $keyDelay, in: 20...500, step: 10) {
                    Text("Delay between keys: \(keyDelay) ms")
                }
            }
            .toggleStyle(.checkbox)
            Divider()
            Text("Auto-type assumes the remote Mac shows its login screen when the session opens. "
                 + "⌃⌥P types the password of the focused Screen Sharing window's server.")
                .font(.caption).foregroundStyle(.secondary)
                .fixedSize(horizontal: false, vertical: true)
            if let error {
                Text(error).font(.caption).foregroundStyle(.red)
            }
            HStack {
                Spacer()
                Button("Done", action: done).keyboardShortcut(.defaultAction)
            }
        }
    }

    private func setLaunchAtLogin(_ on: Bool) {
        do {
            if on { try SMAppService.mainApp.register() } else { try SMAppService.mainApp.unregister() }
            error = nil
        } catch {
            self.error = error.localizedDescription
            launchAtLogin = SMAppService.mainApp.status == .enabled
        }
    }
}
