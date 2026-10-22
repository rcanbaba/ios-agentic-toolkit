# Visual review: Synthetic leaderboard app

Contract: `design-system.json`

Findings: 1 blocker, 3 major

## Leaderboard

Screenshots: `screenshots/leaderboard-light.png` (light), `screenshots/leaderboard-large-type.png` (large-type)

| Id | Severity | Rule | Observation | Fix | Evidence | Decision |
|---|---|---|---|---|---|---|
| V2 | blocker | LAYOUT-OVERFLOW | At the large text size the points keep their full width and the row runs past the right edge | Remove .fixedSize(); give the points layoutPriority(1) and minimumScaleFactor(0.7), and let the name truncate | screenshot: `screenshots/leaderboard-large-type.png`<br>code: `App/Features/Leaderboard/LeaderboardRowView.swift:17` | open |
| V1 | major | TYPE-ROW | The points in every row are as large as the screen title and push the names to a few characters<br>Also check: `App/Features/**/*RowView.swift` | Use .dsFont(.label) with .monospacedDigit() for the points; .display is the screen's hero style | screenshot: `screenshots/leaderboard-light.png`<br>code: `App/Features/Leaderboard/LeaderboardRowView.swift:16`<br>lint: `reports/ds-usage.json` | open |

## Wallet (accepted before)

Screenshots: `screenshots/wallet-light.png` (light)

| Id | Severity | Rule | Observation | Fix | Evidence | Decision |
|---|---|---|---|---|---|---|
| V3 | major | SURFACE-PALETTE | The balance is drawn in system blue, which is not in the palette | DS.Colors.ink for the balance; vermilion is reserved for the primary action | screenshot: `screenshots/wallet-light.png`<br>palette: `reports/palette.json`<br>code: `App/Features/Wallet/WalletCard.swift:12` | open |
| V4 | major | DS-GUIDE: “Keep at most one primaryButton per screen” | Two filled vermilion buttons, stacked under the card | Keep the top-up as primaryButton; the second action becomes secondaryButton | screenshot: `screenshots/wallet-light.png` | open |

## Not checked

- Dark appearance: no dark screenshots were captured
- Wallet loading and error states: need a failing backend

