import Foundation
import Testing
@testable import VNCBar

struct ConnectorTests {
    let server = Server(name: "Build", host: "203.0.113.10", port: 15944, username: "alex")

    @Test func encodesEveryReservedCharacter() {
        let url = Connector.url(for: server, password: "p@ss:w/rd ı#%")
        #expect(url?.absoluteString == "vnc://alex:p%40ss%3Aw%2Frd%20%C4%B1%23%25@203.0.113.10:15944")
    }

    @Test func roundTripsThroughURLComponents() throws {
        let password = "ğüş!@#$%^&*()+=:;/?"
        let url = try #require(Connector.url(for: server, password: password))
        let parts = try #require(URLComponents(url: url, resolvingAgainstBaseURL: false))
        #expect(parts.user == "alex" && parts.password == password && parts.port == 15944)
    }

    @Test func noPasswordLeavesItOut() {
        #expect(Connector.url(for: server, password: nil)?.absoluteString == "vnc://alex@203.0.113.10:15944")
        #expect(Connector.url(for: server, password: "")?.absoluteString == "vnc://alex@203.0.113.10:15944")
    }
}
