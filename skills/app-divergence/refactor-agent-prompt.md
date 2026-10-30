# Refactor agent prompt template

Used by the `app-divergence` skill, step 4. One agent per group of files, all
in parallel. Fill every `{{...}}` placeholder.

---

You refactor existing Swift code so that it reads like this app's own code,
**without changing what it does**. Another agent will compare your result
with the original, method by method; any behavior difference is sent back.

Your files (edit only these; other agents own every other file):
{{FILES}}

Vocabulary (use these names for anything you rename): {{VOCABULARY}}
Banned words in new names: {{BANNED}}

You may:
- rename private and internal members, local variables, parameters' internal
  names and private nested types to the vocabulary;
- reorder declarations and group them under `// MARK:` sections;
- extract a helper **only from code that already exists verbatim**, and merge
  verbatim duplicates into one helper;
- split a long SwiftUI `body` into private subviews or computed properties
  that contain the same code;
- rewrite comments.

You must not:
- change the order of side effects, `Task` / `await` boundaries, actor or
  queue hops, `[weak self]` captures, `defer` blocks or `@Published`
  assignment order;
- change any string literal, number, key, identifier sent to the server, or
  analytics value;
- change public or internal type names, `init` signatures and argument
  labels, members other files use ({{EXTERNAL_MEMBERS}}), protocol
  requirements, `@objc` names, CodingKeys or Codable property names;
- change modifier order, focus and keyboard handling, animation timing or
  conditions in views;
- fix bugs, add error handling, add or remove logging. If you see a bug,
  report it instead.
- run the project build. `swiftc -parse` on your files is allowed.

Return:
1. Files changed, and per file the renames you made (old → new).
2. Helpers extracted or merged, each with the lines it replaced.
3. Anything you were unsure preserves behavior, with `file:line`.
4. Pre-existing bugs you noticed (not fixed), with `file:line` and the
   observable effect.
