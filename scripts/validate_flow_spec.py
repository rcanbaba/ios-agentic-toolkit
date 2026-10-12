#!/usr/bin/env python3
"""Validate flow specs against the contract and the feature inventory.

Deterministic gate of the flow-spec skill. Two layers:
  1. Structural: schema_lite subset applied to schemas/flow-spec.schema.json
     (ids, file:line evidence on transitions, interruptions, failures and bugs).
  2. Semantic:
     - transitions reference known states (or * as from) and known events
     - every state is reachable from the first state; every event is used (warning)
     - related_features exist in inventory.json
     - identifier completeness: every api_methods / ws_incoming / ws_outgoing identifier
       of the related features appears in the spec (event identifiers, transition
       actions, interruption or failure behavior) or in excluded_identifiers with a reason
     - acceptance tests cover happy_path and every INV-/INT-/FH- id; covers refer to existing ids
     - unique ids for states, events, invariants, interruptions, failures, decisions, tests
     - with --require-decisions: every open_decision has a decision

Usage: validate_flow_spec.py <spec.json>... [--migration-dir <dir>] [--inventory <inventory.json>]
                             [--schema <schema.json>] [--require-decisions]
  The inventory defaults to <migration-dir>/inventory/inventory.json (default dir: .migration).
Exit code 0 = all valid (warnings allowed), 1 = invalid, 2 = usage/IO error.
"""

import json
import re
import sys
from collections import Counter
from pathlib import Path

from schema_lite import check_schema

DEFAULT_SCHEMA = Path(__file__).resolve().parent.parent / "schemas" / "flow-spec.schema.json"
IDENTIFIER_FIELDS = ["api_methods", "ws_incoming", "ws_outgoing"]


def check_semantics(spec, feats, require_decisions, errors, warnings):
    states = [s["id"] for s in spec["states"]]
    events = [e["id"] for e in spec["events"]]
    groups = {
        "states": states, "events": events,
        "invariants": [x["id"] for x in spec["invariants"]],
        "interruptions": [x["id"] for x in spec["interruptions"]],
        "failure_handling": [x["id"] for x in spec["failure_handling"]],
        "open_decisions": [x["id"] for x in spec["open_decisions"]],
        "acceptance_tests": [x["id"] for x in spec["acceptance_tests"]],
    }
    for group, ids in groups.items():
        dupes = sorted({i for i in ids if ids.count(i) > 1})
        if dupes:
            errors.append(f"{group}: duplicate ids {dupes}")

    state_set, event_set = set(states), set(events)
    used_events = Counter()
    for t in spec["transitions"]:
        label = f"transition {t['from']} --{t['event']}--> {t['to']}"
        if t["from"] != "*" and t["from"] not in state_set:
            errors.append(f"{label}: unknown from-state")
        if t["to"] not in state_set:
            errors.append(f"{label}: unknown to-state")
        if t["event"] not in event_set:
            errors.append(f"{label}: unknown event")
        used_events[t["event"]] += 1
    for e in events:
        if not used_events[e]:
            warnings.append(f"event {e} is not used by any transition")

    reach, changed = {states[0]}, True
    while changed:
        changed = False
        for t in spec["transitions"]:
            if (t["from"] == "*" or t["from"] in reach) and t["to"] not in reach:
                reach.add(t["to"])
                changed = True
    unreachable = sorted(state_set - reach)
    if unreachable:
        errors.append(f"states unreachable from initial state {states[0]}: {unreachable}")

    unknown = [f for f in spec["related_features"] if f not in feats]
    if unknown:
        errors.append(f"unknown related_features {unknown}")
    text = "\n".join([e["identifier"] for e in spec["events"]]
                     + [a for t in spec["transitions"] for a in t["actions"]]
                     + [x["current_behavior"] for x in spec["interruptions"] + spec["failure_handling"]])
    excluded = {x["identifier"] for x in spec["excluded_identifiers"]}
    for fid in spec["related_features"]:
        for field in IDENTIFIER_FIELDS:
            for ident in feats.get(fid, {}).get(field, []):
                if ident not in excluded and not re.search(r"(?<![A-Za-z0-9_])" + re.escape(ident) + r"(?![A-Za-z0-9_])", text):
                    errors.append(f"identifier {field}:{ident} of related feature {fid} appears nowhere in the spec and is not excluded")
    unused_exclusions = sorted(excluded - {i for fid in spec["related_features"] for field in IDENTIFIER_FIELDS for i in feats.get(fid, {}).get(field, [])})
    if unused_exclusions:
        warnings.append(f"excluded_identifiers not used by any related feature: {unused_exclusions}")

    coverable = set(groups["invariants"]) | set(groups["interruptions"]) | set(groups["failure_handling"])
    covered = Counter()
    for at in spec["acceptance_tests"]:
        for ref in at["covers"]:
            if ref != "happy_path" and ref not in coverable:
                errors.append(f"{at['id']}: covers unknown id {ref}")
            covered[ref] += 1
    if not covered["happy_path"]:
        errors.append("acceptance_tests: no test covers happy_path")
    uncovered = sorted(coverable - set(covered))
    if uncovered:
        errors.append(f"acceptance_tests: no test covers {uncovered}")

    if require_decisions:
        undecided = [d["id"] for d in spec["open_decisions"] if not d.get("decision")]
        if undecided:
            errors.append(f"open_decisions without a decision: {undecided}")


def validate(spec, feats, schema, require_decisions):
    errors, warnings = [], []
    check_schema(spec, schema, "$", errors)
    if not errors:
        check_semantics(spec, feats, require_decisions, errors, warnings)
    return errors, warnings


def main(argv):
    args = argv[1:]
    mig, inventory_path, schema_path, require = Path(".migration"), None, DEFAULT_SCHEMA, False
    for flag in ("--migration-dir", "--inventory", "--schema"):
        if flag in args:
            i = args.index(flag)
            value = Path(args[i + 1])
            del args[i:i + 2]
            if flag == "--migration-dir":
                mig = value
            elif flag == "--inventory":
                inventory_path = value
            else:
                schema_path = value
    if "--require-decisions" in args:
        require = True
        args.remove("--require-decisions")
    if not args:
        print("usage: validate_flow_spec.py <spec.json>... [--migration-dir <dir>] [--inventory <inventory.json>] [--schema <schema.json>] [--require-decisions]", file=sys.stderr)
        return 2
    inventory_path = inventory_path or mig / "inventory" / "inventory.json"
    try:
        schema = json.loads(Path(schema_path).read_text())
        feats = {f["id"]: f for f in json.loads(Path(inventory_path).read_text())["features"]}
        specs = [(p, json.loads(Path(p).read_text())) for p in args]
    except (OSError, json.JSONDecodeError, KeyError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    ok = True
    for path, spec in specs:
        errors, warnings = validate(spec, feats, schema, require)
        summary = ""
        if not errors:
            summary = f" (states {len(spec['states'])}, events {len(spec['events'])}, transitions {len(spec['transitions'])}, tests {len(spec['acceptance_tests'])})"
        print(f"{'INVALID' if errors else 'VALID'}: {path}{summary}")
        for e in errors:
            print(f"  - error: {e}")
        for w in warnings:
            print(f"  - warning: {w}")
        ok &= not errors
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
