final class APIClient {
    static let shared = APIClient()
    func fetchProfile() async throws {}
    func sendGift(id: Int) async throws {}
    func buyTokens(productId: String) async throws {}
    // Never called, already dead in the legacy app.
    func legacyPing() async throws {}
}
