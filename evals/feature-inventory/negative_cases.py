#!/usr/bin/env python3
"""Negative cases for the migration scripts: each one breaks a fresh copy of the
pocket-threads example in one way and checks that the scripts refuse or report it
instead of silently corrupting data. Every case comes from a defect seen in a real run.

Usage: python3 evals/feature-inventory/negative_cases.py
Exit code 0 = every case behaves as expected, 1 = at least one does not.
"""

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

TOOLKIT = Path(__file__).resolve().parents[2]
EXAMPLE = TOOLKIT / "examples" / "migrations" / "pocket-threads"
SCRIPTS = TOOLKIT / "scripts"
FAILURES = []


def run(script, *args):
    r = subprocess.run([sys.executable, str(SCRIPTS / script), *map(str, args)], capture_output=True, text=True)
    return r.returncode, r.stdout + r.stderr


def load(p):
    return json.loads(Path(p).read_text())


def save(p, d):
    Path(p).write_text(json.dumps(d, indent=1, ensure_ascii=False) + "\n")


def case(name):
    def wrap(fn):
        tmp = Path(tempfile.mkdtemp())
        try:
            shutil.copytree(EXAMPLE, tmp / "ex")
            fn(tmp / "ex" / "migration")
            print(f"ok    {name}")
        except AssertionError as exc:
            FAILURES.append(name)
            print(f"FAIL  {name}: {exc}")
        finally:
            shutil.rmtree(tmp)
        return fn
    return wrap


def expect(cond, msg):
    if not cond:
        raise AssertionError(msg)


def verification(m, patches=(), checks=()):
    save(m / "verification" / "neg.json", {
        "schema_version": "1.0", "scope": "neg", "verified_features": [], "patches": list(patches),
        "known_issue_checks": list(checks), "missing_features": [], "summary": "negative case"})


def apply(m, dry=True):
    return run("apply_verification.py", "--migration-dir", m, *(["--dry-run"] if dry else []), "--scope", "neg")


def flow_of(m, fid):
    return next(f for p in (m / "inventory" / "parts").glob("*.json") for f in load(p)["features"] if f["id"] == fid)["flow"]


EV = "Features/Thread/ThreadViewModel.swift:13"


# --- apply_verification.py: replace semantics and the patch gate

@case("replace without old is rejected")
def _(m):
    verification(m, [{"feature_id": "send-message", "field": "flow", "action": "replace", "value": f"x ({EV})", "evidence": EV}])
    code, out = apply(m)
    expect(code == 1 and "requires 'old'" in out, out)


@case("replace whose old matches nothing changes nothing and is listed for review")
def _(m):
    before = flow_of(m, "send-message")
    verification(m, [{"feature_id": "send-message", "field": "flow", "action": "replace",
                      "old": "open: fetches messages and joins", "value": f"open: rewritten ({EV})", "evidence": EV}])
    code, out = apply(m, dry=False)
    skipped = load(m / "verification" / "applied.json")["skipped"]
    expect(code == 1 and skipped and skipped[0]["why"] == "replace_no_unique_match", out)
    expect(flow_of(m, "send-message") == before, "flow changed although nothing matched (appended?)")


@case("replace whose old prefix matches several items changes nothing")
def _(m):
    part = m / "inventory" / "parts" / "messaging.json"
    d = load(part)
    next(f for f in d["features"] if f["id"] == "send-message")["flow"] = [f"open a ({EV})", f"open b ({EV})"]
    save(part, d)
    verification(m, [{"feature_id": "send-message", "field": "flow", "action": "replace",
                      "old": "open", "value": f"open c ({EV})", "evidence": EV}])
    code, out = apply(m, dry=False)
    expect(code == 1 and flow_of(m, "send-message") == [f"open a ({EV})", f"open b ({EV})"], out)


@case("joined, unknown and prefixed identifiers are rejected")
def _(m):
    for value in ["sendMessage, markThreadRead", "teleport"]:
        verification(m, [{"feature_id": "send-message", "field": "api_methods", "action": "add", "value": value, "evidence": EV}])
        expect(apply(m)[0] == 1, f"accepted {value!r}")
    for value in [f"api_methods: markThreadRead ({EV})", f"[persistence] draft key ({EV})"]:
        verification(m, [{"feature_id": "send-message", "field": "flow", "action": "add", "value": value, "evidence": EV}])
        code, out = apply(m)
        expect(code == 1 and "another field encoded" in out, f"accepted {value!r}: {out}")


@case("flow steps without existing file:line evidence are rejected")
def _(m):
    for value in ["close: leave the thread", "close: leave (Features/Thread/ThreadViewModel.swift:999)", "close (Nope.swift:1)"]:
        verification(m, [{"feature_id": "send-message", "field": "flow", "action": "add", "value": value, "evidence": EV}])
        expect(apply(m)[0] == 1, f"accepted {value!r}")


@case("source_files patches must be real paths, one per item")
def _(m):
    verification(m, [{"feature_id": "send-message", "field": "source_files", "action": "add",
                      "value": "REPLACES [Features/Thread/ThreadView.swift]: Features/Thread/ThreadView.swift, Shared/RelativeDateFormatter.swift",
                      "evidence": EV}])
    code, out = apply(m)
    expect(code == 1 and "source_file_notes" in out, out)


@case("known-issue check without a unique match annotates nothing and is listed")
def _(m):
    verification(m, checks=[{"feature_id": "thread-list", "issue": "load failure is ignored entirely",
                             "verdict": "false_positive", "evidence": EV}])
    code, out = apply(m, dry=False)
    state = load(m / "verification" / "applied.json")
    expect(code == 1 and state["annotate_unmatched"], out)
    issues = next(f for f in load(m / "inventory" / "parts" / "messaging.json")["features"] if f["id"] == "thread-list")["known_issues"]
    expect(not any(i.startswith("[") for i in issues), f"annotated a non-matching issue: {issues}")


# --- reconcile_inventory.py

@case("bare route call-site patterns are refused")
def _(m):
    config = load(m / "enumerations.config.json")
    config["call_site_patterns"]["app_routes"] = ["\\b\\.{name}\\b"]
    save(m / "enumerations.config.json", config)
    code, out = run("reconcile_inventory.py", "--migration-dir", m)
    expect(code == 2 and "bare route" in out, out)


@case("an identifier called from files of more than two features is ambiguous, not attached")
def _(m):
    src = m.parent / "source" / "Features" / "Settings" / "SettingsView.swift"
    src.write_text(src.read_text() + "\nfunc openLatest() { Router.shared.navigate(to: .thread(id: \"latest\")) }\n")
    for part in (m / "inventory" / "parts").glob("*.json"):
        d = load(part)
        for f in d["features"]:
            f["app_routes"] = [r for r in f["app_routes"] if r != "thread"]
        save(part, d)
    run("extract_enumerations.py", m / "enumerations.config.json", "--out", m / "inventory" / "enumerations.json")
    run("merge_inventory.py", "--migration-dir", m)
    code, out = run("reconcile_inventory.py", "--migration-dir", m)
    rec = load(m / "inventory" / "reconciliation.json")
    amb = [a for a in rec["ambiguous"] if a["identifier"] == "thread"]
    expect(code == 1 and amb and len(amb[0]["candidates"]) == 3, out)
    owners = [f["id"] for p in (m / "inventory" / "parts").glob("*.json") for f in load(p)["features"] if "thread" in f["app_routes"]]
    expect(not owners, f"attached anyway to {owners}")


@case("merging duplicates keeps scalars and rewrites references")
def _(m):
    over = load(m / "reconcile.overrides.json")
    over["merge_features"] = [["realtime-connection", "thread-list"]]
    save(m / "reconcile.overrides.json", over)
    code, out = run("reconcile_inventory.py", "--migration-dir", m, "--overrides", m / "reconcile.overrides.json")
    feats = {f["id"]: f for p in (m / "inventory" / "parts").glob("*.json") for f in load(p)["features"]}
    kept = feats["realtime-connection"]
    expect("thread-list" not in feats and kept["criticality"] == "high", f"criticality {kept['criticality']}")
    expect("Merged from thread-list:" in kept["summary"], kept["summary"])
    scopes = load(m / "verification" / "scopes.json")
    expect("thread-list" not in scopes["messaging-core"]["features"] and "realtime-connection" in scopes["messaging-core"]["features"], scopes)
    # a patch written against the dropped id still lands on the kept feature
    verification(m, [{"feature_id": "thread-list", "field": "states_and_edge_cases", "action": "add",
                      "value": "merged-id check", "evidence": EV}])
    code, out = apply(m, dry=False)
    kept = next(f for p in (m / "inventory" / "parts").glob("*.json") for f in load(p)["features"] if f["id"] == "realtime-connection")
    expect(code == 0 and "merged-id check" in kept["states_and_edge_cases"], out)


# --- validate_flow_spec.py

def spec_errors(m, mutate, *flags):
    p = m / "flow-specs" / "send-message.json"
    d = load(p)
    mutate(d)
    save(p, d)
    return run("validate_flow_spec.py", p, "--migration-dir", m, *flags)


@case("flow spec evidence must point inside an existing file")
def _(m):
    code, out = spec_errors(m, lambda d: d["transitions"][0].update(evidence="Features/Threads/ThreadListViewModel.swift:400"))
    expect(code == 1 and "outside the file" in out, out)
    code, out = spec_errors(m, lambda d: d["as_is_bugs"][0].update(evidence="Gone.swift:3"))
    expect(code == 1 and "no such source file" in out, out)


@case("uncovered invariants, unreachable states and blank exclusion reasons are errors")
def _(m):
    # mutations accumulate within a case, so each step expects only its own error
    code, out = spec_errors(m, lambda d: d["states"].append({"id": "orphan", "actor": "user", "description": "x", "ui": "", "resources": ""}))
    expect(code == 1 and "unreachable" in out, out)
    code, out = spec_errors(m, lambda d: d.update(entry_states=["idle", "orphan"]))
    expect(code == 0, f"entry_states did not make the state reachable: {out}")
    code, out = spec_errors(m, lambda d: d["excluded_identifiers"].append({"identifier": "typing", "reason": "  "}))
    expect(code == 1 and "needs a reason" in out, out)
    code, out = spec_errors(m, lambda d: d["excluded_identifiers"].pop())
    code, out = spec_errors(m, lambda d: [t.update(covers=["behavior"]) for t in d["acceptance_tests"] if "INV-1" in t["covers"]])
    expect(code == 1 and "INV-1" in out, out)


@case("a decision aligning with a legacy app needs evidence; base_flow must exist")
def _(m):
    code, out = spec_errors(m, lambda d: d["open_decisions"][1].update(decision="Align with the legacy app"), "--require-decisions")
    expect(code == 1 and "legacy" in out, out)
    code, out = spec_errors(m, lambda d: d["open_decisions"][1].update(decision_evidence="Features/Thread/ThreadView.swift:17"), "--require-decisions")
    expect(code == 0, out)
    code, out = spec_errors(m, lambda d: d.update(base_flow="join-thread"))
    expect(code == 1 and "base_flow" in out, out)


# --- render_pending.py

@case("decided questions are never listed again; deferred ones are")
def _(m):
    p = m / "flow-specs" / "send-message.json"
    d = load(p)
    d["open_decisions"][1]["decision"] = "Keep the draft and show the error"
    save(p, d)
    run("render_pending.py", m / "PENDING_DECISIONS.md", p)
    text = (m / "PENDING_DECISIONS.md").read_text()
    expect("OD-2" not in text.split("BEGIN per-flow")[1] and "OD-3" in text, text)
    expect(text.count("BEGIN per-flow") == 1, "generated block duplicated")


# --- extract_enumerations.py

@case("enum case comments, helpers and unconsumed messages")
def _(m):
    run("extract_enumerations.py", m / "enumerations.config.json", "--out", m / "inventory" / "enumerations.json")
    keys = load(m / "inventory" / "enumerations.json")["keys"]
    names = [c["name"] for c in keys["ws_incoming_message_types"]["cases"]]
    expect(names == ["messageReceived", "typingStarted", "threadUpdated", "readReceipt"], names)
    expect(keys["api_client_methods"].get("excluded") == ["fetchData"], keys["api_client_methods"])
    expect(next(c for c in keys["api_client_methods"]["cases"] if c["name"] == "reportMessage")["path"] == "report", "multi-line path missed")
    expect([c["name"] for c in keys["ws_parsed_but_unconsumed"]["cases"]] == ["readReceipt"], keys["ws_parsed_but_unconsumed"])


@case("extractor kinds: delegate callbacks, dependencies, plist and string keys, notifications")
def _(m):
    root = m.parent / "fixture"
    files = {
        "App/Media.swift": (
            "final class Media: NSObject, MediaEngineDelegate {\n"
            "    func mediaEngine(_ engine: MediaEngine, didJoinChannel channel: String, withUid uid: UInt) {}\n"
            "    @objc func mediaEngineDidStop(_ engine: MediaEngine) {}\n}\n"
            "extension Notification.Name { static let didLogin = Notification.Name(\"didLogin\") }\n"
            "func login() { NotificationCenter.default.post(name: .didLogin, object: nil) }\n"),
        "Pods/Headers/MediaEngine.h": (
            "@protocol MediaEngineDelegate <NSObject>\n@optional\n"
            "- (void)mediaEngine:(MediaEngine *)engine didJoinChannel:(NSString *)channel withUid:(NSUInteger)uid;\n"
            "- (void)mediaEngineDidStop:(MediaEngine *)engine;\n"
            "- (void)mediaEngine:(MediaEngine *)engine didLeaveWithStats:(Stats *)stats;\n@end\n"),
        "Podfile.lock": "PODS:\n  - Alamofire (5.8.0)\n  - Firebase/Core (10.0.0):\n    - FirebaseCore\n\nDEPENDENCIES:\n  - Alamofire\n",
        "App.xcodeproj/project.pbxproj": '\t\trepositoryURL = "https://github.com/example/ImageKit.git";\n',
        "Vendor/Stream.xcframework/Info.plist": "",
        "App/Info.plist": '<?xml version="1.0"?><plist version="1.0"><dict><key>NSCameraUsageDescription</key><string>x</string></dict></plist>',
        "App/en.lproj/Localizable.strings": '"welcome.title" = "Hi";\n',
    }
    for rel, text in files.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(text)
    (root / "migration").mkdir()
    save(root / "migration" / "enumerations.config.json", {"source_root": "App", "extract": [
        {"key": "callbacks", "kind": "conformance", "field": None, "protocol": "MediaEngineDelegate", "requirements": ["Pods/**/*.h"]},
        {"key": "sdks", "kind": "dependencies", "field": None},
        {"key": "plist", "kind": "plist", "field": None, "files": ["**/Info.plist"]},
        {"key": "strings", "kind": "strings", "field": None, "files": ["**/*.strings"]},
        {"key": "notifications", "kind": "regex", "field": None, "pattern": "static\\s+let\\s+(\\w+)\\s*=\\s*Notification\\.Name",
         "counts": {"posters": "post\\(name:\\s*\\.{name}\\b"}}]})
    code, out = run("extract_enumerations.py", root / "migration" / "enumerations.config.json", "--out", root / "migration" / "e.json")
    expect(code == 0, out)
    k = load(root / "migration" / "e.json")["keys"]
    expect([c["name"] for c in k["callbacks"]["cases"]] == ["mediaEngine:didJoinChannel:withUid:", "mediaEngineDidStop:"], k["callbacks"])
    expect(k["callbacks"]["not_implemented"] == ["mediaEngine:didLeaveWithStats:"], k["callbacks"])
    expect({(c["name"], c["via"]) for c in k["sdks"]["cases"]} == {("Alamofire", "cocoapods"), ("Firebase", "cocoapods"),
                                                                   ("ImageKit", "spm"), ("Stream", "vendored")}, k["sdks"])
    expect([c["name"] for c in k["plist"]["cases"]] == ["NSCameraUsageDescription"], k["plist"])
    expect([c["name"] for c in k["strings"]["cases"]] == ["welcome.title"], k["strings"])
    expect(k["notifications"]["cases"][0]["posters"] == 1, k["notifications"])


if __name__ == "__main__":
    print(f"\n{'all cases pass' if not FAILURES else str(len(FAILURES)) + ' failing: ' + ', '.join(FAILURES)}")
    sys.exit(1 if FAILURES else 0)
