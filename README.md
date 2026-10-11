# ios-agentic-toolkit

A growing toolkit of supervised agentic workflows for real iOS engineering
work, packaged as a [Claude Code](https://docs.claude.com/en/docs/claude-code)
plugin.

This is not an iOS app and not one giant autonomous agent. It is a set of
engineering rules, skills, contracts, deterministic tools and evaluations that
Claude Code uses **inside your own iOS repositories**. Each workflow covers one
area of iOS work: crash investigation, UI implementation, release preparation
and so on. A workflow is added only when a real use case needs it, and it is
refined by grading real runs.

## Workflows

| Workflow | What it does | Status |
|---|---|---|
| [Crash Investigation & Fix](docs/workflows/crash-investigation.md) | Read-only Crashlytics investigation with ranked, evidence-backed hypotheses, followed by an approval-gated minimal fix and honest verification | **Implemented**, refined in real use |
| Design System Extraction | 3–10 UI reference screenshots → structured, reusable design-system contract | Planned |
| SwiftUI UI Implementation | Implements UI from a design-system contract within the existing project architecture | Planned |
| Visual Review | Compares implemented UI with design-system rules and feeds violations back to implementation | Planned |
| App Store Metadata | Description, subtitle, keywords and review notes | Planned |
| App Review Assistant | Prepares responses to App Review | Planned |
| Release Precheck | Pre-submission checks | Planned |
| iOS Bug Triage | Structured triage of bug reports | Planned |
| Firebase/APNs Configuration Audit | Configuration checks | Planned |
| Legacy Feature Change Safety | Safe changes in large legacy codebases | Planned |

Planned items are ideas, not features. Each will be designed when a real task
needs it.

## Principles

- **Hybrid deterministic + agentic.** Behavior that can be specified reliably
  is a script, schema or validator. Agentic reasoning is used only where
  judgment is needed: interpreting incomplete evidence, exploring unfamiliar
  code, deciding what to inspect next, forming and ranking hypotheses.
- **Supervised autonomy.** Read-only and analysis steps may run on their own.
  Changing code requires an explicit request and an approved plan, and risky
  or broad changes require confirmation.
- **Evidence over plausibility.** Observations, inferences, hypotheses and
  confirmed facts are kept apart. "Insufficient evidence" is a valid outcome,
  and "it compiles" is never reported as "it is fixed".
- **Earned complexity.** No agents, subagents, MCP servers or LLM calls are
  added because they are possible. Each must justify itself, and the
  justification is documented.
- **Evaluated, not demoed.** Every workflow has a rubric, and real runs are
  graded against it.

## Building blocks

| Concept | Meaning | Where |
|---|---|---|
| **Rule** | A domain-independent engineering constraint shared by all workflows | [`rules/`](rules/ios-engineering.md) |
| **Skill** | Knowledge and procedure for one task, loaded on demand | [`skills/<name>/SKILL.md`](skills/) |
| **Agent / subagent** | A separate reasoning context, used only when isolation or focus clearly pays off | None yet |
| **Contract** | Structured output that a later step, human or eval consumes | [`schemas/`](schemas/) |
| **Tool** | A deterministic program the agent runs and observes | [`scripts/`](scripts/), `xcodebuild`, `simctl`, `git` |
| **Workflow** | Skills, deterministic steps and human decisions put together for one area of work | [`docs/workflows/`](docs/workflows/) |
| **Eval** | Rubric and fixtures that measure a workflow's behavior | [`evals/`](evals/) |

## Anatomy of a workflow

Workflows share a shape: agentic work that produces a contract, deterministic
checks on that contract, a human decision before anything changes, and
external feedback before anything is called done.

```mermaid
flowchart LR
    IN["Input<br/>(evidence, screenshots,<br/>requirements)"] --> A["Agentic skill<br/>explore · reason · decide"]
    A --> C["Contract<br/>(JSON + readable report)"]
    C --> D{{"Deterministic check<br/>schema · validator"}}
    D -- invalid --> A
    D -- valid --> H{"Human decision"}
    H -- stop --> X([No change])
    H -- approve --> B["Action skill<br/>smallest change"]
    B --> F["External feedback<br/>build · test · simulator"]
    F -- fails --> B
    F -- passes --> R["Report of what was<br/>actually verified"]
```

Not every workflow needs every stage. A read-only workflow ends at the
contract, for example. But new workflows start from this shape rather than
from a blank page.

## How the toolkit grows

```mermaid
flowchart LR
    U["Real task in a<br/>real iOS project"] --> W["Run the workflow"]
    W --> G["Grade the run<br/>against the eval rubric"]
    G --> L["Extract generalizable<br/>lessons"]
    L --> T["Change skills, rules,<br/>contracts, evals"]
    T --> W
```

Real projects and their data stay private. Only sanitized lessons and
synthetic examples enter this repository. The crash workflow's
[lessons from real use](docs/workflows/crash-investigation.md#lessons-from-real-use)
show this loop in practice.

## Installation

In any iOS repository:

```
/plugin marketplace add rcanbaba/ios-agentic-toolkit
/plugin install ios-agentic-toolkit@ios-agentic-toolkit
```

While developing the toolkit, load a local checkout instead:

```sh
cd ~/path/to/your-ios-app
claude --plugin-dir ~/path/to/ios-agentic-toolkit
```

Usage is described per workflow; start with
[Crash Investigation & Fix](docs/workflows/crash-investigation.md#usage).

## Repository structure

```
.claude-plugin/        plugin + marketplace manifests
rules/                 shared, domain-independent engineering rules
skills/<name>/         one folder per skill (SKILL.md + on-demand references)
schemas/               contracts between steps
scripts/               deterministic tools
docs/workflows/        one document per workflow: design, usage, decisions, lessons
examples/<area>/       synthetic inputs and expected outputs
evals/<skill>/         rubrics and fixture plans
```

## Safety and privacy

This repository is public. It never contains company source code, real crash
reports, user identifiers, production stack traces, Firebase configuration,
service-account files or keys. Examples and eval fixtures are synthetic.
Workflow outputs are written inside the target repository, in git-excluded
locations.

## License

[MIT](LICENSE)
