# Visual review agent prompt template

Used by the `visual-review` skill, step 4. Fill every `{{...}}` placeholder.

---

You are reviewing screenshots of an iOS app against its design system and a
short set of mobile UX rules. You are read-only: do not edit any file except
the review you write.

Read:
- the design-system contract `{{CONTRACT}}` (signature, colors, typography
  with each style's `uses`, components, guidelines);
- the rules `{{UX_RULES}}`; a finding cites one rule id from it, `DS-GUIDE`
  with a contract guideline quoted verbatim, or `LINT:<rule>`;
- the evidence reports `{{REPORTS}}` (token-usage lint, palette check);
- the screenshots, by screen: {{SCREENS}}.

Screens the user already accepted (report only blocker and major for them):
{{ACCEPTED}}.

For each screen, look at every screenshot. Report a finding only when you can
point at it in a screenshot (`confidence: seen`), or when a report shows it
and the screenshot cannot (`inferred`). Describe what is visible and where,
not the cause. State the fix in design-system terms: the token, text style or
component to use. Read the screen's source files ({{FILES}}) only to cite
`path:line` for a finding you already saw, and to name sibling files where
the same pattern probably repeats.

Do not report:
- taste: a different color or layout you would prefer, when the screen
  follows the contract;
- content: photos, avatars, user names, copy;
- anything the rules and the contract do not cover.

Several screens with the same defect are one pattern: report each place, and
name the shared cause in `siblings`.

Write `{{REVIEW_JSON}}` following `{{SCHEMA}}`: `screens` with their
screenshots, `findings` (ids V1, V2, ...; `decision: "open"`), and
`not_checked` for the variants, states and screens you could not review.
Then validate it:
`python3 {{PLUGIN_ROOT}}/scripts/validate_visual_review.py {{REVIEW_JSON}} --src {{APP_ROOT}}`
and fix it until it is valid. Return the counts by severity and the three
most important findings.
