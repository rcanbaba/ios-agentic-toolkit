---
name: app-divergence
description: Turn an iOS app that was ported from another app into its own codebase without changing its behavior. Agrees a new domain vocabulary and the wire boundary with the user, then runs measured phases of verified identifier renames, file splits and behavior-preserving refactors by parallel agents with independent equivalence reviewers, coordinates endpoint and socket renames with the backend, and closes with the app identity checklist. Writes only in the fork. Use after app-port, when the user wants a rebranded or forked app to stop being a copy of the original.
argument-hint: "<phase: vocabulary | rename <area> | refactor <area> | measure | backend | identity> [original root] [fork root]"
allowed-tools: Read, Glob, Grep, Edit, Write, Agent, Bash(python3 *rename_identifiers.py *), Bash(python3 *verify_rename.py *), Bash(python3 *check_split.py *), Bash(python3 *find_string_bindings.py *), Bash(python3 *similarity.py *), Bash(rsync *), Bash(git mv *), Bash(git status*), Bash(git diff*), Bash(xcodebuild *), Bash(xcrun simctl *)
---

# App Divergence

After a port, the fork behaves exactly like the original because it **is**
the original's code. This skill makes it its own codebase in small,
verified phases: names first, structure second, and never behavior. In the
run this was derived from, about 3,500 identifiers, 1,300 localization keys,
311 endpoint paths, 127 socket events and 654 network model types moved to a
new vocabulary in ~30 phases, and raw line overlap with the original fell
from about 62 % to 52 % with the wire format byte-identical. What was left
is explained, not hidden: see step 6.

Read the shared rules first: `${CLAUDE_PLUGIN_ROOT}/rules/ios-engineering.md`
(if not substituted, find `rules/ios-engineering.md` at the plugin root).
Templates next to this file: `refactor-agent-prompt.md`,
`equivalence-review-prompt.md`, `identity-checklist.md`. Scripts in
`${CLAUDE_PLUGIN_ROOT}/scripts/`: `rename_identifiers.py`,
`verify_rename.py`, `check_split.py`, `find_string_bindings.py`,
`similarity.py`.

Input: $ARGUMENTS

## Ground rules

- **Behavior stays the original's.** A divergence phase changes names and
  structure only. A behavior change happens only when the decision log says
  so, as its own commit. Bugs found on the way (reviewers find many) go to
  the ledger as "pre-existing, not fixed"; the user decides each one.
- **The wire is fixed.** JSON keys, CodingKeys, request and response field
  names, endpoint paths, socket event and action names, push types, deep link
  values, UserDefaults keys, localization keys the server sends, analytics
  values, asset names loaded by string and third-party SDK class names do
  not change in this skill. Swift names that double as wire names go in the
  map's `protected` list. Endpoint and socket names change only with the
  backend (step 7).
- **Order:** move and verify (app-port, done), then rename, then
  restructure. Areas where a mistake costs most (realtime or streaming
  sessions, payments, sign-in) are renamed first and restructured later or
  never; ask the user per area. The network layer comes last, because its
  model names ripple into feature code.
- **The original is read-only.** Commit only when the user asks, with the
  fork repository's own identity; never the identity of another project.
- **Tools and baselines live in the repo or the ledger,** never only in a
  scratchpad: in the real run a scratchpad was lost and its tools had to be
  recovered from transcripts.

## 1. Vocabulary and boundary → human decides

1. List the original's domain concepts from the feature inventory and the
   type names (features, screens, managers, models, routes): one row per
   concept with its current names in code.
2. Ask for banned words (for example words that make a feature sound paid or
   adult, or that echo the original brand) and propose 3–4 new names per
   concept without them. **The user picks.** Do not reuse a previous fork's
   vocabulary: the next fork is measured against that one too.
3. Write the vocabulary table and the wire boundary (what is protected and
   why) into the fork's porting folder, next to the ledger, and the banned
   words into every map's `banned` list.

## 2. Rename phase (one area at a time)

1. **Baseline:** copy the fork's sources before touching them
   (`rsync -a --include='*/' --include='*.swift' --exclude='*' <src>/ <baseline>/`),
   kept until the phase is verified.
2. **Map:** `renames/NN-<area>.json` with `rename`, `protected`, `banned`.
   Types, members, routes and app-layer cases in the new vocabulary. Before
   adding a member name, check:
   - it is not a protocol requirement with a default implementation (a
     renamed conformer silently falls back to the default);
   - it is not an `@objc` / selector name, a Codable property without a
     CodingKeys entry, or a name a xib or storyboard references;
   - no one-letter names; rename those inside a refactor, where a reviewer
     reads them.
3. **Apply:** `python3 scripts/rename_identifiers.py renames/NN.json --src <fork src> --dry-run`,
   then without `--dry-run`. `--files` limits it to listed files (for
   example two view models with same-named copies). A refusal lists every
   collision; resolve each by hand, never by forcing. Read every warning
   about enum cases turned into text: asset names, keys or log values built
   from case names change at runtime.
4. **Move files and folders** to match (`git mv`), and rename the
   localization keys only if that is a separate, agreed phase with its own
   map.
5. **Verify:**
   `python3 scripts/verify_rename.py renames/NN.json --src <fork src> --baseline <baseline>`
   must report 0 problems (only mapped tokens changed, same lines, same
   strings), then
   `python3 scripts/find_string_bindings.py --src <fork root> --catalog <each Assets.xcassets> [--asset-literals REGEX]`:
   every xib/storyboard `customClass`, plist class name, `NSClassFromString`
   and string-loaded asset must resolve. Then the project's build.
6. **Ledger:** the map, the counts, the verification results, anything
   protected on purpose.

## 3. Split phase (large files)

Split by concern into `Type+Concern.swift` extensions: cut line ranges
verbatim, then remove `private` / `fileprivate` only where the compiler says
a member is inaccessible. Prove it:
`python3 scripts/check_split.py --baseline <copy of the file> --parts <every resulting file>`
must report 0 problems. Read `access_relaxed`: when a `private` overload
becomes visible, a call can bind to a different overload with no error, so
relax overload sets together and check behavior after the build. A
`private extension` or `private(set)` needed elsewhere is relaxed the same
way, after a search for name clashes.

## 4. Refactor phase (agents, then reviewers)

1. Partition the area into groups (one view model and its views; a manager
   and its helpers) that do not share files.
2. Spawn one agent per group, in parallel, with `refactor-agent-prompt.md`
   filled in. Agents edit only their files and **do not build**; parallel
   builds of one project collide.
3. Integrate: build once, fix integration errors.
4. Freeze a copy of the result and spawn independent reviewers with
   `equivalence-review-prompt.md`: they compare each changed method with the
   baseline and return "equivalent" or the exact difference. A reviewer did
   not write the code it reviews. Fix every difference, re-review what
   changed.
5. Pre-existing bugs the reviewers list go to the ledger, not into the code.
6. **Rewrites** (replacing an implementation rather than restructuring it,
   for example formatters and small utilities) need a differential test:
   compile the old and the new implementation side by side in a scratch
   harness, run the same input corpus under several locales, languages and
   time zones, and diff the outputs. Keep the old implementation where any
   input differs and the difference is not agreed.
7. Smoke on the simulator with DEBUG-only launch arguments that reach deep
   screens directly (for example `-openFirst<Screen>`), so each phase can be
   checked in a minute.

## 5. Measure

After each phase:
`python3 scripts/similarity.py --original <original src> --fork <fork src> --renames renames/*.json --md <porting folder>/similarity.md`.
Report raw and normalized line and fingerprint overlap, the per-area table
and the matched lines by kind. Never use a file-pair metric: renamed and
split files pair with nothing and make the number look far better than it is.

## 6. Know the floor

Explain the remaining overlap with the "by kind" table before proposing more
work. In the real run, of 52 points: about 23 were generic lines every Swift
app shares (`guard let self else { return }`, modifier chains) and cannot
fall; about 12 were wire field names (model properties, CodingKeys, accesses
like `.ownerId`), which fall only if the backend renames fields or the app
adds its own domain models; about 17 were carried-over logic, concentrated
in a few areas. Propose the next lever by expected gain per risk (a domain
model layer for the busiest area, a real redesign of one flow, generated
network models) and let the user decide when it is enough.

## 7. Backend renames

1. **Names first, code second.** Write `backend/endpoint-socket-rename.md`
   and `.json`: the vocabulary, then old → new for every endpoint path,
   socket event, socket action and channel/scope value (all four lists; a
   forgotten scope value made the backend reject every heartbeat), each with
   a "used by the app" column. Share it early: the backend needs time.
2. In the app, case names follow the new names while **raw values keep the
   old strings**. When the backend ships, one script replaces the raw values
   from the JSON; nothing else changes.
3. Verify: every new path answers something other than 404 on staging; log
   the socket `type` names received in DEBUG and join a live session; report
   unknown socket types as non-fatal errors, since a decoder that drops
   unknown types hides a missed rename.
4. Request and response field names stay, unless the backend publishes a
   field rename list the same way.

## 8. Identity

Before the fork ships, walk `identity-checklist.md` with the user: bundle
id, team, Firebase project, sign-in providers, URL schemes, associated
domains, entitlements, icon, permission texts, SDK keys, and the backend
settings that must know the new app.

## 9. Report

In chat, per phase: what was renamed or restructured (map names, counts),
the verification results (verify, bindings, split, build, reviews), the
similarity before and after, pre-existing bugs found, and what is next. End
with what was not verified (for example flows that need a camera or a
second device).
