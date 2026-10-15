import SwiftUI

struct ServerEditor: View {
    let store: ServerStore
    let target: PopoverView.EditTarget
    let done: () -> Void

    @State private var server: Server
    @State private var password = ""
    @State private var error: String?
    @State private var confirmDelete = false

    init(store: ServerStore, target: PopoverView.EditTarget, done: @escaping () -> Void) {
        self.store = store
        self.target = target
        self.done = done
        if case .existing(let server) = target {
            _server = State(initialValue: server)
        } else {
            _server = State(initialValue: Server(name: "", host: "", username: ""))
        }
    }

    private var isNew: Bool { target == .new }
    private var hasStoredPassword: Bool { store.withPassword.contains(server.id) }

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text(isNew ? "Add server" : "Edit server").font(.headline)
            Form {
                TextField("Name", text: $server.name, prompt: Text("Build Mac 1"))
                TextField("Host", text: $server.host, prompt: Text("203.0.113.10 or vnc://host:port"))
                    .onChange(of: server.host) { _, text in fill(from: text) }
                TextField("Port", value: $server.port, format: .number.grouping(.never))
                TextField("Username", text: $server.username)
                SecureField("Password", text: $password,
                            prompt: Text(hasStoredPassword ? "Unchanged" : "Password"))
            }
            if let error {
                Text(error).font(.caption).foregroundStyle(.red)
            }
            HStack {
                if !isNew {
                    Button(confirmDelete ? "Really delete?" : "Delete", role: .destructive) {
                        if confirmDelete { delete() } else { confirmDelete = true }
                    }
                }
                Spacer()
                Button("Cancel", action: done).keyboardShortcut(.cancelAction)
                Button("Save", action: save).keyboardShortcut(.defaultAction)
            }
        }
    }

    /// A pasted `vnc://user:pass@host:port` is split into the fields at once; a password in it goes
    /// to the password field and never stays in the host field. A typed `host:port` is split on
    /// save, so the field does not jump while the port is being typed.
    private func fill(from text: String) {
        guard text.lowercased().hasPrefix("vnc://"), let parsed = ParsedAddress.parse(text) else { return }
        apply(parsed)
    }

    private func apply(_ parsed: ParsedAddress) {
        if let port = parsed.port { server.port = port }
        if let username = parsed.username { server.username = username }
        if let pasted = parsed.password { password = pasted }
        server.host = parsed.host
    }

    private func save() {
        server.name = server.name.trimmingCharacters(in: .whitespaces)
        server.host = server.host.trimmingCharacters(in: .whitespaces)
        if let parsed = ParsedAddress.parse(server.host), parsed.host != server.host { apply(parsed) }
        do {
            try store.save(server, password: password.isEmpty ? nil : password)
            password = ""
            done()
        } catch {
            self.error = error.localizedDescription
        }
    }

    private func delete() {
        do {
            try store.delete(server)
            done()
        } catch {
            self.error = error.localizedDescription
        }
    }
}
