import Foundation

/// SYNTHETIC EXAMPLE CODE for ios-agentic-toolkit. Not from a real app.
@MainActor
final class QualitySheetViewModel: ObservableObject {
    @Published var selected: StreamQuality
    private let session: PlayerSession
    private let analytics: Analytics

    init(session: PlayerSession, current: StreamQuality, analytics: Analytics) {
        self.session = session
        self.selected = current
        self.analytics = analytics
        analytics.log("quality_sheet_opened")
    }

    /// Called from the sheet's onDisappear.
    func didDismiss() {
        analytics.log("quality_sheet_dismissed")
        session.applyQuality(selected)
    }
}
