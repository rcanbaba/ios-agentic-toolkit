import SwiftUI

struct PopoverView: View {
    let store: ServerStore
    let accessibility: Accessibility
    let connect: (Server) -> Void
    let typePassword: (Server) -> Void
    @State private var editing: EditTarget?

    enum EditTarget: Equatable {
        case new
        case existing(Server)
    }

    var body: some View {
        Group {
            if let editing {
                ServerEditor(store: store, target: editing) { self.editing = nil }
            } else {
                list
            }
        }
        .padding()
        .frame(width: 380)
    }

    private var list: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Text("VNCBar").font(.headline)
                Spacer()
                Button { editing = .new } label: { Image(systemName: "plus") }
                    .help("Add a server")
            }
            if !accessibility.isTrusted {
                HStack {
                    Label("Typing passwords needs the Accessibility permission.", systemImage: "hand.raised")
                        .font(.caption)
                    Spacer()
                    Button("Grant…") { accessibility.request() }
                }
                .padding(8)
                .background(.orange.opacity(0.15), in: RoundedRectangle(cornerRadius: 6))
            }
            if let error = store.loadError {
                Text(error).font(.caption).foregroundStyle(.red)
            }
            if store.servers.isEmpty {
                Text("No servers yet. Add one with +.")
                    .foregroundStyle(.secondary)
                    .frame(maxWidth: .infinity, minHeight: 80)
            } else {
                ScrollView {
                    VStack(spacing: 0) {
                        ForEach(store.servers) { server in
                            ServerRow(server: server, hasPassword: store.withPassword.contains(server.id),
                                      connect: { connect(server) }, typePassword: { typePassword(server) },
                                      edit: { editing = .existing(server) })
                            if server.id != store.servers.last?.id { Divider() }
                        }
                    }
                }
                .frame(maxHeight: 420)
                .fixedSize(horizontal: false, vertical: true)
            }
            Divider()
            HStack {
                Spacer()
                Button("Quit") { NSApplication.shared.terminate(nil) }
            }
        }
    }
}

private struct ServerRow: View {
    let server: Server
    let hasPassword: Bool
    let connect: () -> Void
    let typePassword: () -> Void
    let edit: () -> Void

    var body: some View {
        HStack(spacing: 8) {
            VStack(alignment: .leading, spacing: 2) {
                Text(server.name).fontWeight(.medium)
                Text(server.address).font(.caption).foregroundStyle(.secondary)
                if !hasPassword {
                    Label("No password saved", systemImage: "exclamationmark.triangle")
                        .font(.caption2).foregroundStyle(.orange)
                }
            }
            Spacer()
            Button("Connect", action: connect)
            Button("Password", action: typePassword).disabled(!hasPassword)
            Button(action: edit) { Image(systemName: "pencil") }
                .buttonStyle(.borderless)
                .help("Edit")
        }
        .padding(.vertical, 6)
    }
}
