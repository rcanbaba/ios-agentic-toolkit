#!/usr/bin/env python3
"""Mutate the fixture review into invalid ones; the validator must reject each with its error.

Usage: negative_cases.py <review.json> <validate_visual_review.py>  (run from the fixture copy)
"""
import copy
import json
import subprocess
import sys
from pathlib import Path


def finding(doc, fid):
    return next(f for f in doc["findings"] if f["id"] == fid)


CASES = [
    ("unknown rule id", "unknown rule 'TYPE-HUGE'",
     lambda d: finding(d, "V1").update(rule="TYPE-HUGE")),
    ("unknown lint rule", "unknown check_ds_usage rule 'pretty-colors'",
     lambda d: finding(d, "V1").update(rule="LINT:pretty-colors")),
    ("guideline not in the contract", "guideline not found verbatim",
     lambda d: finding(d, "V4").update(guideline="Use one primary button")),
    ("DS-GUIDE without a quote", "DS-GUIDE needs the guideline quoted",
     lambda d: finding(d, "V4").pop("guideline")),
    ("finding on an unknown screen", "unknown screen 'profile'",
     lambda d: finding(d, "V1").update(screen="profile")),
    ("screenshot of another screen", "is not one of screen 'leaderboard''s screenshots",
     lambda d: finding(d, "V1")["evidence"].__setitem__(0, {"kind": "screenshot", "ref": "screenshots/wallet-light.png"})),
    ("missing screenshot file", "screenshot screenshots/leaderboard-dark.png not found",
     lambda d: d["screens"][0]["screenshots"].append({"file": "screenshots/leaderboard-dark.png", "variant": "dark"})),
    ("code line outside the file", "line 400 is outside",
     lambda d: finding(d, "V2")["evidence"].__setitem__(1, {"kind": "code", "ref": "App/Features/Leaderboard/LeaderboardRowView.swift:400"})),
    ("seen without a screenshot", "'seen' needs screenshot evidence",
     lambda d: finding(d, "V2").update(evidence=[{"kind": "code", "ref": "App/Features/Leaderboard/LeaderboardRowView.swift:17"}])),
    ("minor finding on an accepted screen", "was accepted before; report only blocker or major",
     lambda d: finding(d, "V3").update(severity="minor")),
    ("duplicate finding id", "findings: duplicate ids ['V1']",
     lambda d: finding(d, "V2").update(id="V1")),
]


def main():
    review, validator = Path(sys.argv[1]), sys.argv[2]
    base = json.loads(review.read_text())
    failed = 0
    for name, message, mutate in CASES:
        doc = copy.deepcopy(base)
        mutate(doc)
        path = review.with_name("negative.json")
        path.write_text(json.dumps(doc))
        result = subprocess.run([sys.executable, validator, str(path)], capture_output=True, text=True)
        if result.returncode != 1 or message not in result.stdout:
            failed += 1
            print(f"FAIL: {name}: expected exit 1 with '{message}'\n{result.stdout}")
        path.unlink()
    print(f"negative cases: {len(CASES) - failed}/{len(CASES)} rejected as expected")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
