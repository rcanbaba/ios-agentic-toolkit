---
name: remote-mac
description: List the remote Macs saved in the VNCBar menu bar app and connect to one, or type its password into its Screen Sharing window, by opening vncbar:// URLs. Never reads or handles passwords. Use when the user asks to connect to, open, or log in to one of their remote Macs (build machines, test Macs) over Screen Sharing.
argument-hint: "[list | connect <server> | type <server>]"
allowed-tools: Read, Bash(open vncbar://*), Bash(test -d *VNCBar.app), Bash(pgrep -x VNCBar)
---

# Remote Mac

VNCBar (`${CLAUDE_PLUGIN_ROOT}/tools/vnc-bar`, see
`${CLAUDE_PLUGIN_ROOT}/docs/tools/vnc-bar.md`) does the work: it connects with
macOS Screen Sharing, gets through its dialogs and types the password into
the remote login screen. This skill only finds the server and triggers it.

Input: $ARGUMENTS

## Rules

- **Never handle a password.** Do not read the Keychain, do not ask the user
  for a password, and if they paste one, tell them to enter it in VNCBar
  instead and do not repeat it. Passwords exist only in VNCBar.
- `servers.json` holds hosts and user names. Show them only when the user
  asks to list servers; otherwise refer to servers by name.
- Act only on an explicit request for one server. Never connect to several
  servers, or retry, on your own.

## 1. Check the app

`test -d ~/Applications/VNCBar.app`. If it is missing, give the install
command and stop: `${CLAUDE_PLUGIN_ROOT}/tools/vnc-bar/build.sh --install`
(then add servers from its menu bar icon). If `pgrep -x VNCBar` finds
nothing, opening a `vncbar://` URL launches it.

## 2. Find the server

Read `~/Library/Application Support/VNCBar/servers.json`
(`{"version": 1, "servers": [{"name", "host", "port", "username", "windowTitle"?}]}`).

- **list**: a table of name, `username@host:port`, and the learned window
  title if there is one. Done.
- Otherwise match the user's words to one `name` (case-insensitive, then
  a unique partial match). If none or several match, list the candidates and
  ask; never pick one.

## 3. Trigger

Percent-encode the name (space → `%20`, and so on), then:

| Request | Command | What VNCBar does |
|---|---|---|
| connect / open / log in | `open "vncbar://connect/<name>"` | Opens Screen Sharing, continues its dialogs, waits for the login screen and types the password, when auto-type is on in its settings |
| type the password (session already open, Mac locked) | `open "vncbar://type/<name>"` | Types the password into that server's own Screen Sharing window only; nothing if it has none |

## 4. Report

Say which server was triggered and what should happen on screen. You cannot
see the result: VNCBar shows an alert when something fails (no permission,
no window for that server, password rejected). Mention ⌃⌥P for typing the
password into the focused Screen Sharing window later.
