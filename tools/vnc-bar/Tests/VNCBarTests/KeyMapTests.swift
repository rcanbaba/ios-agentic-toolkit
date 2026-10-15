import Testing
@testable import VNCBar

/// Holds for every Latin layout (US, Turkish Q, German, ...), so it does not depend on the machine.
@MainActor
struct KeyMapTests {
    @Test func lettersDigitsAndShift() throws {
        let map = try #require(KeyMap())
        let a = try #require(map.strokes["a"])
        #expect(!a.shift && !a.option)
        #expect(map.strokes["A"] == KeyMap.Stroke(keyCode: a.keyCode, shift: true, option: false))
        #expect(map.unmappable("abcXYZ0123456789") == [])
    }

    @Test func reportsPositionsNotCharacters() throws {
        let map = try #require(KeyMap())
        #expect(map.unmappable("a\u{1F600}b") == [2])
    }
}
