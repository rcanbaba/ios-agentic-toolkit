# Tool: VNCBar

<img src="images/vnc-bar/icon.png" width="96" align="right" alt="VNCBar icon">

**Status:** implemented, used daily · **Code:** [`tools/vnc-bar`](../../tools/vnc-bar) · **Skill:** [`remote-mac`](../../skills/remote-mac/SKILL.md)

A small native macOS menu bar app that connects to a remote Mac over Screen
Sharing **and logs in**, in one click. The `remote-mac` skill lets Claude Code
trigger it ("connect to the release Mac") without ever handling a password.

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="images/vnc-bar/servers-dark.png">
    <img src="images/vnc-bar/servers-light.png" width="380" alt="VNCBar's server list">
  </picture>
</p>

## Why

iOS work often runs on remote Macs: build machines, release machines,
device labs. Reaching one through Screen Sharing is the same routine many
times a day:

| By hand | With VNCBar |
|---|---|
| Finder → Go → Connect to Server, type `vnc://<ip>:<port>` | Click **Connect** (or ⌃⌥P later, or ask Claude Code) |
| Pick the connection type, press Continue | Continue is pressed for you |
| Type the user name and password | Typed for you, when Screen Sharing asks |
| Wait for the remote login screen, type the password **again** | Typed for you after a short delay |

The remote Macs are managed by someone else, so their lock and auto-login
settings cannot change; the second password is unavoidable. Typing it is
the part worth automating.

## How it works

```mermaid
flowchart LR
    U["You"] --> MB["Menu bar popover<br/>Connect · Password"]
    U --> HK["⌃⌥P"]
    CC["Claude Code<br/>remote-mac skill"] -- "open vncbar://connect/&lt;name&gt;" --> URL["URL scheme"]
    MB & HK & URL --> APP["VNCBar"]
    APP --> J[("servers.json<br/>names · hosts · ports<br/>learned window titles")]
    APP --> K[("Keychain<br/>passwords only")]
    APP -- "vnc://user@host:port" --> SS["Screen Sharing"]
    APP -- "Accessibility: press buttons,<br/>find windows, post key events" --> SS
    SS --> R["Remote Mac<br/>login screen"]
```

What **Connect** does, step by step:

```mermaid
sequenceDiagram
    participant V as VNCBar
    participant S as Screen Sharing
    participant R as Remote Mac
    V->>V: note Screen Sharing's open windows
    V->>S: open vnc://user@host:port (no password)
    S-->>V: connection-type dialog (new window)
    V->>S: press Continue (only while Standard is selected)
    opt Screen Sharing asks for credentials
        S-->>V: authentication dialog
        V->>S: type password + Return (once)
    end
    S->>R: connect
    S-->>V: new window showing the remote screen
    V->>V: learn its title (the remote Mac's name) for this server
    V->>V: wait the login delay (3 s)
    V->>R: password + Return, only while that window is focused
```

## Features

<table>
<tr>
<td width="33%" valign="top">

**Servers.** Add, edit and delete. Paste a whole `vnc://user:pass@host:port`
into the host field: it is split into the fields, and the password goes to
the password field. Window titles learned on connect can be forgotten.

</td>
<td width="33%" valign="top">

**Typing.** **Password** types into the server's window. ⌃⌥P types into the
focused Screen Sharing window when it belongs to exactly one server, and
beeps otherwise.

</td>
<td width="33%" valign="top">

**Settings.** Auto-type after connecting, auto-choose Standard, login screen
delay, delay between keys, launch at login.

</td>
</tr>
<tr>
<td valign="top">
<picture>
  <source media="(prefers-color-scheme: dark)" srcset="images/vnc-bar/editor-dark.png">
  <img src="images/vnc-bar/editor-light.png" alt="Editing a server">
</picture>
</td>
<td valign="top">
<picture>
  <source media="(prefers-color-scheme: dark)" srcset="images/vnc-bar/servers-dark.png">
  <img src="images/vnc-bar/servers-light.png" alt="Server list">
</picture>
</td>
<td valign="top">
<picture>
  <source media="(prefers-color-scheme: dark)" srcset="images/vnc-bar/settings-dark.png">
  <img src="images/vnc-bar/settings-light.png" alt="Settings">
</picture>
</td>
</tr>
</table>

Screenshots are rendered from synthetic servers with
`VNCBar --render-screenshots <dir>`, so they never show real hosts.

## Install

Needs macOS 14+, Swift 6 and, preferably, an "Apple Development" signing
identity in the keychain.

```sh
tools/vnc-bar/build.sh --install     # builds, signs, copies to ~/Applications, launches
```

Then click the icon, press **Grant…** for the Accessibility permission, and
add your servers. `CODESIGN_IDENTITY` (name or SHA-1) picks a specific
identity. Without one the app is signed ad-hoc, which changes on every build
and resets the Accessibility permission each time.

## Usage

| From | How |
|---|---|
| Menu bar | **Connect**, **Password**, ✏️ to edit, ⚙️ for settings |
| Anywhere | ⌃⌥P while a Screen Sharing window is in front |
| Shell or other tools | `open "vncbar://connect/Build%20Mac%201"`, `open "vncbar://type/Build%20Mac%201"` |
| Claude Code | `/remote-mac list`, `/remote-mac connect build mac 1`, or just ask |

Diagnostics, run from the installed app's binary
(`~/Applications/VNCBar.app/Contents/MacOS/VNCBar`):

| Command | Prints |
|---|---|
| `--check-leak "<server>"` | Paths of Screen Sharing / Finder files that contain that server's password (never the password) |
| `--dump-windows` | Screen Sharing's window and element tree; text fields only as lengths |
| `--render-screenshots <dir>` | The docs screenshots, from synthetic data |

## Security model

| Concern | Rule |
|---|---|
| Where passwords live | Only the Keychain (generic password, service = bundle id, account = server id). Never in `servers.json`, the URL scheme, logs, alerts or output. |
| Screen Sharing's own records | The `vnc://` URL carries no password, because Screen Sharing stores the URL it was opened with in plaintext (see lessons) |
| Typing into the wrong place | Typing stops the moment the target window is no longer focused. After Connect, nothing is typed unless a **new** session window appeared, so an already logged-in session never receives a password. |
| The URL scheme | Any app or web page can open `vncbar://`. `type` therefore types only into that server's own window, never into whatever is focused. |
| The hotkey | Types only when the focused window matches exactly one server; never guesses |
| Claude Code | The skill reads `servers.json` (no secrets) and opens URLs. It never reads the Keychain and refuses passwords pasted into chat. |

## Design decisions

- **A tool plus a thin skill.** Connecting, finding windows and typing are
  deterministic and need permissions and secrets a model should not hold, so
  they live in a native app. The skill only resolves "the release Mac" to a
  server and opens a URL, the same deterministic + agentic split as the
  workflows.
- **AppKit `NSStatusItem` + `NSPopover`, not `MenuBarExtra`.** The popover must
  be closed programmatically before keys go to another app.
- **Key events, not AppleScript.** `CGEvent` needs only the Accessibility
  permission (no Apple Events prompt). Characters are mapped to key codes and
  Shift/Option on the current layout with `UCKeyTranslate`, the way System
  Events' `keystroke` does; dead keys and the keypad are never used.
- **Buttons are pressed, not typed at.** The connection-type dialog's
  Continue is pressed through Accessibility, and only while Standard is
  selected.
- **Windows are matched by learned title.** Screen Sharing titles a session
  with the remote Mac's name, not its address, so VNCBar learns the title
  when a connect opens a new window, then falls back to host and name, and
  never picks between several candidates.
- **A stable signature.** The Accessibility grant and the Keychain's access
  rules follow the code signature; the build signs with a real identity,
  chosen by SHA-1 because several certificates can share one name.
- **The icon is code.** `Icon/make-icon.swift` draws it and the build turns it
  into an `.icns`, so the repository holds no binary icon.

## Limitations

- Screen Sharing sends key codes; the remote Mac reads them with **its**
  layout. Typing is right when both Macs use the same layout (verified with a
  Turkish Q layout and a password with `i` and symbols).
- Auto-type assumes the remote Mac shows its login screen when the session
  opens. If it may already be unlocked, turn auto-type off and use
  **Password** or ⌃⌥P when needed.
- The fallback for finding Continue (when the dialog has no default button)
  matches the English label.
- IPv6 addresses are not supported in the host field.

## Lessons from real use

| Observed | Change |
|---|---|
| Opening `vnc://user:password@host:port` made Screen Sharing write the password in plaintext to `Screen Sharing Hosts/*.plist` in its container | The URL never carries the password; it is typed into the authentication dialog. `--check-leak` verifies it. |
| Session windows are titled with the remote Mac's name, not its address | Titles are learned on connect, per server |
| A connection-type dialog (Standard / High Performance) appears before connecting | Continue is pressed through Accessibility while Standard is selected |
| The authentication dialog sometimes does not appear (Screen Sharing remembered the credentials) | The connect flow handles both cases and types into the dialog at most once |
| ⌘V did nothing in the popover's text fields | An accessory app needs a main menu with an Edit menu for the standard shortcuts |
| Signing by name failed: several certificates share one "Apple Development" label | The build picks the identity by SHA-1 |
| The keyboard-layout API aborted when tests ran it off the main thread | Key mapping runs on the main actor |
