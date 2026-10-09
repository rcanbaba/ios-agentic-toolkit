---
name: crash-fix
description: Implement and verify the smallest safe fix for an iOS crash that was already investigated by the crash-analysis skill. Consumes .crash-analysis/<issue-id>/analysis.json, proposes a fix plan, waits for approval, edits code, then builds/tests and reports what was actually verified.
argument-hint: "<issue-id>"
disable-model-invocation: true
---

# Crash Fix

Fix a crash that has a validated analysis. Only runs when the user explicitly
invokes `/crash-fix`.

Read the shared rules first: `${CLAUDE_PLUGIN_ROOT}/rules/ios-engineering.md`
(if not substituted, find `rules/ios-engineering.md` at the plugin root).

Issue: $ARGUMENTS

## 1. Load the analysis

1. Read `.crash-analysis/<issue-id>/analysis.json`. If there is no analysis,
   stop and suggest running the `crash-analysis` skill first. Do not
   investigate from scratch here.
2. Validate it:
   `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/validate_analysis.py .crash-analysis/<issue-id>/analysis.json`.
3. Check the gate:
   - `code_change.justified: false` → stop. Explain why the analysis did not
     justify a change and what evidence is missing. Continue only if the user
     explicitly says to proceed anyway; record that override in the report.
   - Otherwise use `conclusion.leading_hypothesis` and `fix_direction` as the
     starting point.
4. Re-read the code in `relevant_code` and `fix_direction.files`. If the
   code no longer matches what the analysis describes (moved, changed on this
   branch), say so before planning.

## 2. Fix plan → human approval

Present a short plan and **wait for approval before editing anything**:

- the change, per file, in one or two sentences each
- why it addresses the leading hypothesis's mechanism (not just the symptom)
- what behavior changes for users or callers, if any
- risks, and any call sites affected
- how it will be verified (build, which tests, simulator steps)

Prefer the smallest change supported by the evidence. Avoid:
- refactors, renames, or architecture changes not required by the fix
- guards that silence the crash without addressing why the state occurred,
  unless the user explicitly accepts a mitigation and it is labeled as one
- dependency version changes without evidence they are the cause

If the fix touches anything listed under rule 11 (risky changes), say so
explicitly in the plan.

## 3. Implement

Make exactly the approved change. If you discover during implementation that
the plan is wrong or incomplete, stop and present the revised plan rather than
silently widening the change.

Add or update a test that exercises the crash path when the project has a
test target where such a test fits naturally. Follow existing test style.

## 4. Verify (external feedback loop)

Determine how to build the project: check the project's CLAUDE.md/README,
otherwise `xcodebuild -list` and ask the user once which scheme and
simulator to use if it is ambiguous.

Loop, at most three iterations:

1. **Build** (`xcodebuild build` or `build-for-testing` with the chosen
   scheme and an available simulator from `xcrun simctl list devices available`).
2. **Run relevant tests** (`-only-testing:` for the affected test targets or
   classes; the full suite only if the change is shared or the user asks).
3. **Runtime check** when it can meaningfully exercise the crash path:
   reproduce the steps from `reproduction.strategy` on a simulator.
4. **Observe** the actual output. On failure, diagnose from the compiler/test
   output, revise the change within the approved scope, and repeat. If a fix
   requires going beyond the approved scope, stop and ask.

After three failed iterations, stop and report what was learned.

## 5. Verification report

Write `.crash-analysis/<issue-id>/verification.md` and summarize it in chat.
Report each level explicitly as **yes / no / not attempted**:

| Level | Result | Evidence |
|---|---|---|
| Compiles | | command + result |
| Relevant tests pass | | which tests |
| New/updated test covers the crash path | | test name |
| Reproduced before fix | | steps / output |
| Not reproduced after fix | | steps / output |
| Root cause | confirmed / probable | why |

Then list the changed files with a one-line reason each, the remaining risks,
and what to monitor in Crashlytics after release (e.g. the issue's event count
on the fixed version).

Never write "fixed" when only the first rows are yes. "Compiles and tests
pass; root cause remains probable until the crash-free rate is confirmed in
production" is the honest form.

Do not commit or push unless the user asks.
