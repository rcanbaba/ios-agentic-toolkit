# iOS Engineering Rules

Shared constraints for every skill in this toolkit. These rules are generic.
Domain knowledge (crash categories, design systems, ...) lives in the skills.

## Changing code

1. **Preserve the existing architecture.** Do not introduce new patterns, layers,
   or dependencies unless the task requires them. A cleaner design being
   possible is not a reason to change one.
2. **Prefer the smallest scoped change** that addresses the evidence. No
   drive-by refactors, renames, or formatting changes in touched files.
3. **Inspect callers and dependencies before changing shared behavior.** Search
   for every call site of a function or type before changing its contract.
4. **Do not modify unrelated files.** Every changed file must be explainable by
   the task.
5. **Follow the project's conventions**: naming, error handling, logging,
   threading idioms, test style. Read neighboring code first.
6. **Do not change public behavior silently.** If a fix changes what users or
   API callers observe, say so explicitly.
7. **Do not change dependency versions** unless evidence shows the dependency is
   the cause.

## Verifying

8. **Build and run relevant tests after implementing.** Report the actual
   commands and results.
9. **Never claim an issue is fixed because code was written or compiled.**
   State exactly what was verified and what remains probabilistic.

## Reasoning

10. **Separate evidence from speculation.** Label statements as observed,
    inferred, hypothesized, or confirmed. "Insufficient evidence" is a valid
    conclusion.

## Safety and autonomy

11. **Ask for human approval before risky or broad changes**: multi-module
    edits, persistence/migration changes, concurrency model changes, security-
    or payment-related code, build settings, dependency changes.
12. **Never expose secrets or credentials.** Do not print, copy, or commit API
    keys, `GoogleService-Info.plist` contents, certificates, tokens, or user
    identifiers. Redact them in reports.
13. **Treat crash reports and production data as private.** Do not copy them
    into public repositories, issues, or commit messages.
