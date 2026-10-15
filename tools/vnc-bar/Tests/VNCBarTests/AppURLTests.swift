import Foundation
import Testing
@testable import VNCBar

struct AppURLTests {
    @Test func parsesBothActions() {
        #expect(AppURL(URL(string: "vncbar://connect/Build%201")!) == AppURL(action: .connect, serverName: "Build 1"))
        #expect(AppURL(URL(string: "VNCBAR://Type/Release")!) == AppURL(action: .type, serverName: "Release"))
    }

    @Test func rejectsEverythingElse() {
        for text in ["vncbar://connect/", "vncbar://connect", "vncbar://delete/Build", "vnc://connect/Build",
                     "vncbar://connect/a/b"] {
            #expect(AppURL(URL(string: text)!) == nil, "\(text)")
        }
    }
}
