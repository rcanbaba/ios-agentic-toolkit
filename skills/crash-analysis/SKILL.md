---
name: crash-analysis
description: Read-only investigation of an iOS crash (Firebase Crashlytics or similar) inside the current iOS repository. Produces ranked, evidence-backed root-cause hypotheses and a structured analysis; never modifies source code. Use when the user shares a crash report, stack trace, Crashlytics issue, or asks why the app crashes.
argument-hint: "[crash report text, or a path to a file containing it]"
allowed-tools: Read, Glob, Grep, Bash(git log *), Bash(git show *), Bash(git blame *), Bash(git diff *), Bash(git check-ignore *), Bash(python3 *validate_analysis.py *)
---

# Crash Analysis

Investigate a crash and produce a structured, evidence-backed analysis.
This skill is **read-only**: it explains the crash, it does not fix it.

Before starting, read the shared rules at
`${CLAUDE_PLUGIN_ROOT}/rules/ios-engineering.md` (if that variable is not
substituted, find `rules/ios-engineering.md` next to this skill's plugin root).
For category-specific signatures and traps, read
`${CLAUDE_SKILL_DIR}/crash-categories.md` when a category becomes relevant,
not up front.

Crash input: $ARGUMENTS

## Read-only contract

- Allowed: reading and searching files, `git log/show/blame/diff`, reading
  build settings and package manifests.
- The only files you may write are the analysis artifacts under
  `.crash-analysis/<issue-id>/` (see Output) and a line in `.git/info/exclude`.
- Do **not** edit source, tests, project files, or dependencies, even for a
  "one-line obvious fix". Do not run builds that modify the workspace.
- If the user asks for a fix during analysis, finish the analysis first and
  point them to `/crash-fix <issue-id>`.

## 1. Intake

Extract what was supplied: crash type / exception / signal, crashed thread
and its frames, other relevant threads, app version/build, OS versions,
devices, event and user counts, custom keys, breadcrumbs/logs.

Firebase Crashlytics specifics:
- The crashed thread is the one marked `Crashed:`. It is often not the main
  thread, even though the main thread is listed first.
- Swift runtime messages (`Fatal error: ...`) usually appear only under
  **Keys** as `crash_info_entry_0`, `crash_info_entry_1`, ... They are often
  the most precise evidence available; quote them verbatim.
- A crash session export (JSON with `logs_and_breadcrumbs`) may be supplied as
  a file. Read the window leading up to `event_timestamp` first, not the
  whole log.
- Most threads in a dump are idle (run loops, `__psynch_cvwait`, worker
  waits). Focus on the crashed thread and any other thread with app frames,
  especially ones blocked on the same queue or object.
- If the issue lists several variants, ask whether the other variants' crashed
  threads differ. They can separate competing hypotheses.

If the first meaningful application frame or the crash type is missing, ask
for it. Otherwise proceed and record gaps in `missing_information`; do not
block on nice-to-have data.

Treat the report as private: do not echo user identifiers, tokens, or emails
back into reports. Redact them as `<redacted>`.

## 2. Investigate (agentic loop)

Work in a loop: **reason about current evidence → decide what single piece of
evidence would most reduce uncertainty → fetch it → record the observation →
reason again.** There is no fixed sequence. Typical moves:

- Find the **first meaningful app frame**. The top frame is often system code
  (`libswiftCore`, `UIKitCore`, `objc_msgSend`, `libdispatch`); the app frame
  below it is where your code made the fatal assumption.
- Search for that symbol, read the function and its surrounding type.
- Read callers when the crash depends on what was passed in or when it was
  called.
- Read lifecycle code (init/deinit, `viewDidDisappear`, `onDisappear`,
  scene/app state transitions, SDK start/stop) when ownership or timing could
  matter.
- Inspect other threads in the report when concurrency is plausible.
- Correlate breadcrumbs and custom keys with code paths: which code emits
  them, and what state do they imply right before the crash?
- `git log -L` / `git log -S` / `git blame` on the crash site when a
  regression is plausible (crash appears from a specific version).
- Inspect SDK integration code when a third-party frame is involved.

Load context **just in time**: follow the chain of evidence from the crash
site outward. Do not read large parts of the repository speculatively.

Stop investigating when one of these holds:
- a hypothesis is supported by multiple independent pieces of evidence and
  no observed evidence contradicts it;
- remaining hypotheses can only be separated by information you cannot get
  from the repo (runtime data, more reports) — record what is needed;
- further reading is not changing your ranking.

## 3. Reasoning discipline

1. Never go from the top stack frame directly to a confident root cause.
2. Keep four kinds of statement apart:
   - **Observed**: in the report, the code, or git history (→ `evidence`).
   - **Inferred**: a conclusion drawn from observations (→ `mechanism`).
   - **Hypothesis**: a candidate root cause with a confidence level.
   - **Confirmed**: only via reproduction or unambiguous code evidence.
3. Generate more than one hypothesis whenever the evidence allows it, rank
   them, and write down what speaks against each.
4. Confidence: **high** = multiple independent observations agree and nothing
   contradicts; **medium** = consistent with evidence but a key link is
   inferred; **low** = plausible, weakly supported.
5. `insufficient_evidence` is a correct, respectable verdict. Prefer it to an
   invented root cause.
6. Recommend a code change (`code_change.justified: true`) only when the
   leading hypothesis is strong enough that a fix would be targeted rather
   than speculative. Defensive guards that merely hide a crash without an
   understood cause are speculative.

## 4. Output

Use a short kebab-case `issue-id` (e.g. `player-quality-nil-engine`).

1. Make sure `.crash-analysis/` is ignored in this repo:
   `git check-ignore -q .crash-analysis/x`. If it is not, append
   `.crash-analysis/` to `.git/info/exclude` (local only; never edit the
   project's tracked `.gitignore`).
2. Write `.crash-analysis/<issue-id>/analysis.json` following
   `${CLAUDE_PLUGIN_ROOT}/schemas/crash-analysis.schema.json`.
3. Validate it:
   `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/validate_analysis.py .crash-analysis/<issue-id>/analysis.json`.
   Fix the JSON until it is valid. Validation failures are feedback about your
   analysis (e.g. a hypothesis citing evidence you never recorded), not just
   formatting.
4. Write `.crash-analysis/<issue-id>/analysis.md`, a readable rendering with
   these sections: Summary, Impact, Crash location, Evidence (table with ids),
   Hypotheses (ranked, each with mechanism, supporting evidence ids, against /
   uncertain), Conclusion, Missing information, Reproduction, Fix direction,
   Verification, Code change justified?
5. In chat, give a concise summary: verdict, leading hypothesis with
   confidence, the key evidence, what is missing, and the path to the report.

End with exactly one of:
- "No code was modified. If you want to proceed, run `/crash-fix <issue-id>`."
- "No code was modified. Evidence is insufficient for a targeted fix; see
  Missing information."
