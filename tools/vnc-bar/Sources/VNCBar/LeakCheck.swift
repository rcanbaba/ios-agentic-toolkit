import Foundation

/// `VNCBar --check-leak <server name>`: searches the places where Screen Sharing and Finder keep
/// recent connections (including "Screen Sharing Hosts", which stores the opening URL) for that
/// server's password (plain, percent-encoded, UTF-16) and prints only
/// the paths of files that contain it. The password itself is never printed.
/// Exit code 0 = not found, 1 = found, 2 = usage error.
@MainActor
enum LeakCheck {
    static func run(serverName: String) -> Int32 {
        let store = ServerStore()
        guard let server = store.server(named: serverName) else {
            print("no server named \(serverName)")
            return 2
        }
        guard let password = Keychain.password(for: server.id), !password.isEmpty else {
            print("\(server.name) has no saved password")
            return 2
        }
        if password.count < 6 {
            print("warning: a password this short may match unrelated bytes")
        }
        var needles = [Data(password.utf8), Data(Connector.encode(password).utf8)]
        needles += [password.data(using: .utf16BigEndian), password.data(using: .utf16LittleEndian)].compactMap { $0 }

        let home = FileManager.default.homeDirectoryForCurrentUser
        let roots = ["Library/Containers/com.apple.ScreenSharing/Data/Library",
                     "Library/Application Support/com.apple.sharedfilelist",
                     "Library/Preferences"].map { home.appendingPathComponent($0) }
        var scanned = 0
        var hits: [String] = []
        for root in roots {
            guard let files = FileManager.default.enumerator(at: root, includingPropertiesForKeys: [.fileSizeKey, .isRegularFileKey]) else {
                print("cannot read \(root.path)")
                continue
            }
            for case let file as URL in files {
                let values = try? file.resourceValues(forKeys: [.fileSizeKey, .isRegularFileKey])
                guard values?.isRegularFile == true, (values?.fileSize ?? 0) < 20_000_000,
                      let data = try? Data(contentsOf: file) else { continue }
                scanned += 1
                if needles.contains(where: { data.range(of: $0) != nil }) {
                    hits.append(file.path.replacingOccurrences(of: home.path, with: "~"))
                }
            }
        }
        print("scanned \(scanned) files")
        if hits.isEmpty {
            print("the password of \(server.name) was not found")
            return 0
        }
        print("the password of \(server.name) was found in:")
        hits.forEach { print("  \($0)") }
        return 1
    }
}
