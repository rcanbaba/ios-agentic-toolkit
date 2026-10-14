#!/usr/bin/env python3
"""Render a flow spec JSON into a readable Markdown file with a mermaid state diagram.

Deterministic step of the flow-spec skill: the JSON is the source of truth, the
Markdown is derived, so the two cannot drift. Writes <flow_id>.md next to each spec,
always from scratch: never edit the .md by hand. Transitions are numbered (T1, T2, ...);
invariants, interruptions and failures show the acceptance tests that cover them; open
decisions show their decision (or "open").

Usage: render_flow_spec.py <spec.json>...
Exit code 0 = rendered, 2 = usage/IO error.
"""

import json
import sys
from pathlib import Path


def cell(text):
    return str(text if text is not None else "").replace("|", "/").replace("\n", " ")


def table(headers, rows):
    out = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    out += ["| " + " | ".join(cell(c) for c in row) + " |" for row in rows]
    return out + [""]


def render(spec):
    covered_by = {}
    for t in spec["acceptance_tests"]:
        for ref in t["covers"]:
            covered_by.setdefault(ref, []).append(t["id"])

    def tests(item_id):
        return ", ".join(covered_by.get(item_id, [])) or "**none**"

    header = f"`{spec['flow_id']}` · actors: {', '.join(spec['actors'])}"
    if spec.get("base_flow"):
        header += f" · extends `{spec['base_flow']}`"
    L = [f"# Flow spec: {spec['title']}", "", header, "",
         "Describes current behavior as implemented (as-is). Target behavior is listed under Open decisions.",
         "Generated from the JSON spec; do not edit.", "",
         "## Related features", "", ", ".join(f"`{f}`" for f in spec["related_features"]), ""]
    if spec.get("scope_notes"):
        L += ["## Scope", ""] + [f"- {n}" for n in spec["scope_notes"]] + [""]
    if spec["preconditions"]:
        L += ["## Preconditions", ""] + [f"- {p}" for p in spec["preconditions"]] + [""]

    L += ["## State diagram", "", "```mermaid", "stateDiagram-v2"]
    L += [f"    [*] --> {e}" for e in spec.get("entry_states") or [spec["states"][0]["id"]]]
    for t in spec["transitions"]:
        src = "[*]" if t["from"] == "*" else t["from"]
        label = t["event"] + (f" [{t['guard']}]" if t.get("guard") else "")
        L.append(f"    {src} --> {t['to']} : {label}")
    L += ["```", ""]

    L += ["## States", ""] + table(["State", "Actor", "Description", "UI", "Resources"],
                                   [(f"`{s['id']}`", s["actor"], s["description"], s["ui"], s["resources"]) for s in spec["states"]])
    L += ["## Events", ""] + table(["Event", "Source", "Identifier", "Payload"],
                                   [(f"`{e['id']}`", e["source"], f"`{e['identifier']}`", ", ".join(e["payload"])) for e in spec["events"]])
    L += ["## Transitions", ""] + table(["#", "From", "Event", "Guard", "Actions", "To", "Evidence"],
                                        [(f"T{n}", t["from"], t["event"], t.get("guard") or "", "; ".join(t["actions"]), t["to"], f"`{t['evidence']}`")
                                         for n, t in enumerate(spec["transitions"], 1)])
    if spec["invariants"]:
        L += ["## Invariants", ""] + table(["Id", "Statement", "Evidence", "Covered by"],
                                          [(i["id"], i["statement"], f"`{i['evidence']}`" if i.get("evidence") else "", tests(i["id"])) for i in spec["invariants"]])
    for key, heading in (("interruptions", "Interruptions"), ("failure_handling", "Failure handling")):
        if spec[key]:
            L += [f"## {heading}", ""] + table(["Id", "Situation", "Current behavior", "Evidence", "Covered by"],
                                              [(x["id"], x["situation"], x["current_behavior"], f"`{x['evidence']}`", tests(x["id"])) for x in spec[key]])
    if spec["cross_flow_interactions"]:
        L += ["## Cross-flow interactions", ""] + [f"- {x}" for x in spec["cross_flow_interactions"]] + [""]
    if spec["as_is_bugs"]:
        L += ["## As-is bugs", ""] + table(["Description", "Evidence", "Impact"],
                                          [(b["description"], f"`{b['evidence']}`", b["impact"]) for b in spec["as_is_bugs"]])
    if spec.get("cross_cutting_decisions"):
        L += ["## Cross-cutting decisions", ""] + table(["Rule", "Statement", "Decision"],
                                                        [(d["id"], d["rule"], d.get("decision") or "undecided") for d in spec["cross_cutting_decisions"]])
    if spec["open_decisions"]:
        L += ["## Open decisions", ""] + table(["Id", "Question", "Current behavior", "Options", "Rule", "Decision"],
                                              [(d["id"], d["question"], d["current_behavior"], " / ".join(d["options"]), d.get("rule") or "", d.get("decision") or "open") for d in spec["open_decisions"]])
    L += ["## Acceptance tests", ""] + table(["Id", "Priority", "Given", "When", "Then", "Covers"],
                                             [(t["id"], t["priority"], t["given"], t["when"], t["then"], ", ".join(t["covers"])) for t in spec["acceptance_tests"]])
    if spec["excluded_identifiers"]:
        L += ["## Excluded identifiers", ""] + [f"- `{x['identifier']}`: {x['reason']}" for x in spec["excluded_identifiers"]] + [""]
    return "\n".join(L).rstrip() + "\n"


def main(argv):
    paths = argv[1:]
    if not paths:
        print("usage: render_flow_spec.py <spec.json>...", file=sys.stderr)
        return 2
    for p in paths:
        try:
            spec = json.loads(Path(p).read_text())
            out = Path(p).with_suffix(".md")
            out.write_text(render(spec))
        except (OSError, json.JSONDecodeError, KeyError) as exc:
            print(f"error: {p}: {exc}", file=sys.stderr)
            return 2
        print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
