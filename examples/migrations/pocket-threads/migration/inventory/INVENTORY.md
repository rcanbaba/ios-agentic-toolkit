# Pocket Threads feature inventory

7 features · core 1 · high 2 · medium 3 · low 1

## Completeness against the code baseline

| Baseline (from code) | Referenced by features |
|---|---|
| api_methods | 6/7 |
| ws_incoming | 3/4 |
| ws_outgoing | 3/3 |
| push_types | 2/3 |
| app_routes | 5/5 |
| source files | 17/17 |

| Informational baseline | Mentioned in features | In specs | Specs only | Not mentioned |
|---|---|---|---|---|
| api_paths | 4/7 | 2 | 0 | `deleteAccount`, `markRead`, `notificationPrefs` |
| ws_parsed_but_unconsumed | 0/1 | 0 | 0 | `readReceipt` |
| localization_keys | 8/9 | 3 | 1 | 0 |

**Identifiers with no caller in the app (candidates for not porting):**

- api_methods: `deleteAccount`
- ws_incoming: `readReceipt`
- push_types: `digest`

## Feature list

### Conversations and realtime (4)

| Feature | Criticality | Roles | Summary |
|---|---|---|---|
| `send-message` Read and send messages in a conversation | core | signed-in | Opens a conversation, joins its realtime channel, shows incoming messages and typing, and sends new messages with one silent retry. |
| `thread-list` Conversation list | high | signed-in | Shows the user's conversations and opens one on tap. Refreshes when the server reports a thread update. |
| `realtime-connection` Realtime socket connection | medium | any | Single shared socket that decodes incoming message types and sends outgoing actions. |
| `report-message` Report a message | medium | signed-in | Long-press a message, enter a reason and submit a report. |

### Settings and push (3)

| Feature | Criticality | Roles | Summary |
|---|---|---|---|
| `push-routing` Push notification routing | high | signed-in | Opens the conversation referenced by a new-message or mention push. Other push types are ignored. |
| `notification-settings` Notification preferences | medium | signed-in | Toggles for new-message and mention notifications, saved to the server on every change. |
| `about-screen` About | low | any | Shows the app version. |

## Core flows

### `send-message` — Read and send messages in a conversation

Opens a conversation, joins its realtime channel, shows incoming messages and typing, and sends new messages with one silent retry.

1. open: fetchMessages, send joinThread, subscribe to incoming messages, then markThreadRead (Features/Thread/ThreadViewModel.swift:13-26)
2. incoming messageReceived appends to the list (Features/Thread/ThreadViewModel.swift:18-19)
3. send: sendMessage, append on success, show error on failure (Features/Thread/ThreadViewModel.swift:29-43)
4. close: send leaveThread when the screen disappears (Features/Thread/ThreadViewModel.swift:54-55, ThreadView.swift:23)

**Edge cases:** send button disabled while sending or when draft is empty; send failure: one silent retry, then 'Could not send' is shown; typing indicator never resets to false

**Depends on:** `thread-list`, `notification-settings`

## Core and high features without a flow spec

- `push-routing`: No spec of its own: it only opens the thread route, whose behavior the send-message spec covers.

## Known issues found during inventory

### Conversations and realtime (6)

- `thread-list`: load failure is swallowed with try? and shows the empty state
- `send-message`: typing action is sent on every keystroke without throttling
- `send-message`: [FALSE_POSITIVE per messaging-core: Features/Thread/ThreadViewModel.swift:54-55 and ThreadView.swift:23 onDisappear] leaveThread is never sent when the screen closes
- `send-message`: peerIsTyping is set true and never reset
- `realtime-connection`: onMessage is a single closure: whoever sets it last wins
- `report-message`: Router.present does not exist in Router.swift; the call in ThreadViewModel.report would not compile

## Source file notes

- `Navigation/Router.swift` (push-routing): shared: every navigating feature calls it

## Open questions

### Conversations and realtime (1)

- Is the silent retry in send intentional or a workaround for flaky networking?
