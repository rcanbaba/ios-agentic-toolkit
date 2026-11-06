# Equivalence review prompt template

Used by the `app-divergence` skill, step 4, after integration and a green
build. One reviewer per group, on a frozen copy, never the agent that wrote
the code. Fill every `{{...}}` placeholder.

---

You check that a refactor did not change behavior. You do not edit code.

Before: {{BASELINE_FILES}} (a copy taken before the refactor)
After: {{CURRENT_FILES}} (a frozen copy of the result)
Renames applied: {{RENAME_MAPS_OR_AGENT_REPORT}}

For every method, initializer, computed property, closure and view `body` in
"before", find its counterpart in "after" (renamed, moved to a helper or a
subview, or merged with a verbatim duplicate) and compare them as code that
runs:

- the same calls with the same arguments, in the same order, on the same
  actor or queue, with the same `Task` / `await` boundaries and captures;
- the same conditions, early returns, `defer`s, error paths and default
  values;
- the same strings, numbers, keys and values sent to the server;
- for views: the same modifiers in the same order, the same conditions,
  identity (`id`, `ForEach` data), focus, gestures and animations;
- for a merged helper: every former call site passes what it passed before;
- for a renamed member: it is not a protocol requirement with a default
  implementation, and no string, xib, selector or `String(describing:)`
  depended on the old name.

Answer per group:
- **equivalent**, or
- **different**: each difference with before `file:line`, after `file:line`
  and the observable effect.

List separately any pre-existing bug you noticed in "before" (present in
both), with `file:line` and its effect. Those are not differences.
