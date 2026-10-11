#!/usr/bin/env python3
"""Validate a crash-analysis JSON file against the toolkit contract.

Deterministic gate between the crash-analysis and crash-fix skills.
Two layers:
  1. Structural: the dependency-free JSON Schema subset in schema_lite.py,
     applied to schemas/crash-analysis.schema.json.
  2. Semantic: cross-field rules a schema cannot express (evidence references,
     ranking, verdict consistency).

Usage: validate_analysis.py <analysis.json> [--schema <schema.json>]
Exit code 0 = valid, 1 = invalid, 2 = usage/IO error.
"""

import json
import sys
from pathlib import Path

from schema_lite import check_schema

DEFAULT_SCHEMA = Path(__file__).resolve().parent.parent / "schemas" / "crash-analysis.schema.json"


def check_semantics(doc, errors):
    evidence_ids = [e["id"] for e in doc["evidence"]]
    hypotheses = doc["hypotheses"]
    hypothesis_ids = [h["id"] for h in hypotheses]
    conclusion = doc["conclusion"]
    verdict = conclusion["verdict"]
    leading = conclusion["leading_hypothesis"]

    for label, ids in (("evidence", evidence_ids), ("hypothesis", hypothesis_ids)):
        dupes = {i for i in ids if ids.count(i) > 1}
        if dupes:
            errors.append(f"duplicate {label} ids: {sorted(dupes)}")

    for h in hypotheses:
        for ref in h["supporting_evidence"]:
            if ref not in evidence_ids:
                errors.append(f"{h['id']}: references unknown evidence {ref}")

    ranks = sorted(h["rank"] for h in hypotheses)
    if ranks != list(range(1, len(hypotheses) + 1)):
        errors.append(f"hypothesis ranks must be 1..{len(hypotheses)} without gaps, got {ranks}")

    if verdict == "insufficient_evidence":
        if doc["code_change"]["justified"]:
            errors.append("code_change.justified must be false when verdict is insufficient_evidence")
        if not doc["missing_information"]:
            errors.append("missing_information must list what is needed when verdict is insufficient_evidence")
    else:
        if leading is None:
            errors.append(f"verdict {verdict} requires a leading_hypothesis")
        elif leading not in hypothesis_ids:
            errors.append(f"leading_hypothesis {leading} is not a known hypothesis")
        else:
            top = next(h for h in hypotheses if h["id"] == leading)
            if top["rank"] != 1:
                errors.append(f"leading_hypothesis {leading} must have rank 1")
            if verdict == "root_cause_confirmed" and top["confidence"] != "high":
                errors.append("root_cause_confirmed requires the leading hypothesis to have high confidence")

    if doc["code_change"]["justified"]:
        if doc["fix_direction"] is None:
            errors.append("code_change.justified requires a fix_direction")
        if not doc["verification"]:
            errors.append("code_change.justified requires at least one verification step")


def main(argv):
    args = argv[1:]
    schema_path = DEFAULT_SCHEMA
    if "--schema" in args:
        i = args.index("--schema")
        schema_path = Path(args[i + 1])
        del args[i:i + 2]
    if len(args) != 1:
        print("usage: validate_analysis.py <analysis.json> [--schema <schema.json>]", file=sys.stderr)
        return 2
    try:
        schema = json.loads(Path(schema_path).read_text())
        doc = json.loads(Path(args[0]).read_text())
    except (OSError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    errors = []
    check_schema(doc, schema, "$", errors)
    if not errors:
        check_semantics(doc, errors)

    if errors:
        print(f"INVALID: {args[0]}")
        for e in errors:
            print(f"  - {e}")
        return 1
    print(f"VALID: {args[0]}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
