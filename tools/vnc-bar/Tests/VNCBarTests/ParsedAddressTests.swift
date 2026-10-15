import Testing
@testable import VNCBar

struct ParsedAddressTests {
    @Test func vncURLWithEverything() {
        #expect(ParsedAddress.parse(" vnc://alex:p%40ss%3Aw0rd@203.0.113.10:15944 ")
                == ParsedAddress(host: "203.0.113.10", port: 15944, username: "alex", password: "p@ss:w0rd"))
    }

    @Test func vncURLWithoutCredentialsOrPort() {
        #expect(ParsedAddress.parse("vnc://203.0.113.10") == ParsedAddress(host: "203.0.113.10"))
        #expect(ParsedAddress.parse("VNC://mac.example.com:5901") == ParsedAddress(host: "mac.example.com", port: 5901))
    }

    @Test func hostAndPort() {
        #expect(ParsedAddress.parse("203.0.113.10:15944") == ParsedAddress(host: "203.0.113.10", port: 15944))
        #expect(ParsedAddress.parse("mac.example.com") == ParsedAddress(host: "mac.example.com"))
    }

    @Test func rejected() {
        for text in ["", "vnc://", "203.0.113.10:0", "203.0.113.10:99999", "203.0.113.10:abc",
                     "two words", "host/path", "user@host"] {
            #expect(ParsedAddress.parse(text) == nil, "\(text)")
        }
    }
}
