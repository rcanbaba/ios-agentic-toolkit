# Migration decisions

| Date | Topic | Decision |
|---|---|---|
| 2026-01-15 | Dead identifiers (`deleteAccount`, `digest`, `readReceipt`) | Not ported unless a feature needs them; confirm with the backend team. |
| 2026-01-15 | Bugs found in inventory and flow specs | Discuss case by case while porting each feature; no fixes in the current app. |
| 2026-01-15 | A1 resync after interruption | Yes: after background, network loss or socket reconnect, re-join realtime channels and resync state from the server. |
| 2026-01-15 | Default rule | Replicate current behavior unless decided otherwise. |
| 2026-01-15 | send-message OD-2, OD-3 | Deferred to porting; default rule applies. |
