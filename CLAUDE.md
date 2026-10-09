# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

A Claude Code **plugin** (not an iOS app) with reusable agentic iOS engineering
workflows. It is used from *other* iOS repositories (`/plugin install` or
`claude --plugin-dir <this repo>`). This repo is where the toolkit is
developed. V1 contains only the crash workflow; everything else in the README
roadmap is intentionally unimplemented.

## Layout and how the parts connect

- `skills/crash-analysis/SKILL.md`: read-only investigation; writes
  `.crash-analysis/<issue-id>/analysis.{json,md}` in the *target* repo.
- `skills/crash-fix/SKILL.md`: `disable-model-invocation: true` (user-only
  `/crash-fix`); consumes `analysis.json`, requires plan approval, writes
  `verification.md`.
- `schemas/crash-analysis.schema.json`: the contract between the two skills.
  Changing it means updating `scripts/validate_analysis.py` (semantic rules),
  both skills, and the example `analysis.json` together.
- `rules/ios-engineering.md`: shared, domain-independent rules. Skills load
  it via `${CLAUDE_PLUGIN_ROOT}`; crash-specific knowledge belongs in the skill.

## Commands

```sh
# Validate an analysis against the contract (stdlib-only Python)
python3 scripts/validate_analysis.py examples/crashes/player-quality-nil-engine/analysis.json

# Validate plugin/marketplace manifests and skill frontmatter
claude plugin validate .
claude plugin validate .claude-plugin/plugin.json
claude plugin validate skills

# Try the plugin inside a real iOS repo
cd <ios-repo> && claude --plugin-dir <path-to-this-repo>
```

## Rules for working on this repo

- **Git identity:** commits must be authored as `rcanbaba <rcanbabaoglu@gmail.com>`
  (set in repo-local git config). Check `git config user.email` before committing.
- **Public repo:** never add real crash reports, company code, production stack
  traces, user identifiers, Firebase configs or keys. Examples and eval
  fixtures must be synthetic; strip real data even if the user pastes it while
  iterating on a skill.
- **Grow from real use:** add a skill, script, schema field or subagent only
  when a real use case needs it, and explain why in the README's Design
  decisions. Do not scaffold roadmap items or create empty directories.
- **Deterministic first:** if a behavior can be specified reliably, make it a
  script or a validator rule rather than prose in a skill.
- Repo content is written in English.
