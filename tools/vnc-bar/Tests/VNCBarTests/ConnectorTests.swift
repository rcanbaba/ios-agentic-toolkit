import Foundation
import Testing
@testable import VNCBar

struct ConnectorTests {
    @Test func urlCarriesUserButNeverPassword() {
        let server = Server(name: "Build", host: "203.0.113.10", port: 15944, username: "alex")
        #expect(Connector.url(for: server)?.absoluteString == "vnc://alex@203.0.113.10:15944")
    }

    @Test func encodesReservedCharactersInUserName() throws {
        let server = Server(name: "Build", host: "203.0.113.10", port: 5900, username: "a@b:c/ı")
        let url = try #require(Connector.url(for: server))
        #expect(url.absoluteString == "vnc://a%40b%3Ac%2F%C4%B1@203.0.113.10:5900")
        #expect(URLComponents(url: url, resolvingAgainstBaseURL: false)?.user == "a@b:c/ı")
    }

    @Test func encodeKeepsOnlyUnreservedCharacters() {
        #expect(Connector.encode("p@ss:w/rd ı#%-._~") == "p%40ss%3Aw%2Frd%20%C4%B1%23%25-._~")
    }
}
