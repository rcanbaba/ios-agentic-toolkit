import UIKit

/// Owns the playback engine for the currently open stream.
/// SYNTHETIC EXAMPLE CODE for ios-agentic-toolkit. Not from a real app.
final class PlayerSession {
    private var engine: PlaybackEngine!
    private let analytics: Analytics

    init(analytics: Analytics) {
        self.analytics = analytics
        NotificationCenter.default.addObserver(
            self, selector: #selector(handleDidEnterBackground),
            name: UIApplication.didEnterBackgroundNotification, object: nil)
    }

    func start(stream: StreamDescriptor) {
        engine = PlaybackEngine(stream: stream)
        engine.start()
        analytics.log("player_started")
    }

    /// Releases the engine to free decoder resources while in background.
    /// Playback is restarted by the player screen on the next play action.
    @objc private func handleDidEnterBackground() {
        engine?.stop()
        engine = nil
        analytics.log("player_engine_released")
        analytics.setKey("engine_alive", false)
    }

    func applyQuality(_ quality: StreamQuality) {
        engine.setQuality(quality)
        analytics.log("quality_applied")
    }
}
