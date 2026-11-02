"""One daily QA gate, at most two targeted repairs, and a final publish decision."""

from contextlib import contextmanager
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from html import unescape
from html.parser import HTMLParser
import json
import math
import os
import re
import shutil
import signal
import subprocess
import sys
import threading
import time


class StageFailure(RuntimeError):
    def __init__(self, message, code=1):
        super().__init__(message)
        self.code = code


def budget(deadline, limit):
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise StageFailure("Overall Codex/QA time budget exhausted; refusing publication", 124)
    return min(remaining, limit)


def execute(command, workspace, trace, timeout, prompt=None):
    """Bound the whole process group, including any browser/server children."""
    with trace.open("w") as output:
        with subprocess.Popen(command, cwd=workspace, stdin=subprocess.PIPE,
                              stdout=output, stderr=subprocess.STDOUT, text=True,
                              start_new_session=True) as process:
            try:
                process.communicate(prompt, timeout=timeout)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()
                raise StageFailure(f"Stage timed out; private trace: {trace}", 124)
    return process.returncode


def validate_config(workspace, config):
    qa = config["qa"]
    if type(qa["max_repair_attempts"]) is not int or not 0 <= qa["max_repair_attempts"] <= 2:
        raise ValueError("Daily QA permits at most two repair attempts")
    for name in ["review_timeout_seconds", "repair_timeout_seconds",
                 "total_timeout_seconds", "browser_timeout_seconds"]:
        if type(qa[name]) not in (int, float) or not math.isfinite(qa[name]) or qa[name] <= 0:
            raise ValueError(f"QA {name} must be positive")
    for name in ["qa.md", "heal.md"]:
        if not (workspace / "pipelines/codex-v1" / name).is_file():
            raise ValueError(f"Missing daily QA prompt: {name}")
    if not (workspace / "scripts/check-entry-browser.cjs").is_file():
        raise ValueError("Missing headless QA checker")


def entry_path(workspace, slug):
    if not isinstance(slug, str) or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", slug):
        raise ValueError("Expected one valid entry slug")
    path = workspace / "site/entries" / slug
    if path.is_symlink() or not path.is_dir():
        raise ValueError(f"Missing regular entry directory: {slug}")
    return path


class DraftTransaction:
    """Quarantine rejected new entries so a later git add cannot publish them."""

    def __init__(self, workspace, run, existing=None):
        self.workspace, self.run, self.existing = workspace, run, existing
        entries = workspace / "site/entries"
        self.before = {path.name for path in entries.iterdir()} if entries.exists() else set()
        self.shared = {}
        for name in ["site/index.html", "state/history.json"]:
            path = workspace / name
            self.shared[name] = path.read_bytes() if path.exists() else None
        if existing:
            shutil.copytree(entry_path(workspace, existing), run / "original-entry")

    def rollback(self):
        entries = self.workspace / "site/entries"
        new = {path.name for path in entries.iterdir()} - self.before if entries.exists() else set()
        for slug in sorted(new | ({self.existing} if self.existing else set())):
            path = entries / slug
            if path.exists():
                destination = self.run / "rejected" / slug
                destination.parent.mkdir(exist_ok=True)
                if path.is_dir() and not path.is_symlink():
                    shutil.copytree(path, destination)
                    shutil.rmtree(path)
                else:
                    path.unlink()
        if self.existing:
            shutil.copytree(self.run / "original-entry", entries / self.existing)
        for name, contents in self.shared.items():
            path = self.workspace / name
            if contents is None:
                path.unlink(missing_ok=True)
            else:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(contents)
        print(f"codex: rejected draft archived privately at {self.run}; gallery/history restored", file=sys.stderr)


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *_args):
        pass


@contextmanager
def preview(workspace):
    server = ThreadingHTTPServer(("127.0.0.1", 0), partial(QuietHandler, directory=str(workspace / "site")))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def technical_checks(workspace, slug, directory, base, config, deadline):
    directory.mkdir()
    checks = []
    commands = [
        ("metadata", [sys.executable, "scripts/build-entry-metadata.py", "site", slug], 120),
        ("static", ["bash", "scripts/validate-entry.sh", "site", slug], 120),
        ("browser", ["node", "scripts/check-entry-browser.cjs", base, slug, str(directory)],
         config["browser_timeout_seconds"]),
    ]
    for name, command, limit in commands:
        log = directory / f"{name}.log"
        code = execute(command, workspace, log, budget(deadline, limit))
        checks.append({"name": name, "passed": code == 0, "log": str(log)})
    regressions = editorial_regressions(workspace, slug)
    regression_path = directory / "editorial-regressions.json"
    regression_path.write_text(json.dumps(regressions, indent=2, ensure_ascii=False) + "\n")
    checks.append({"name": "editorial-regressions", "passed": regressions["passed"], "log": str(regression_path)})
    report = {"passed": all(check["passed"] for check in checks), "checks": checks}
    (directory / "technical.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


def editorial_regressions(workspace, slug):
    """Carry explicit human findings forward; a model pass cannot discard them."""
    ledger = workspace / "pipelines/codex-v1/editorial-regressions.json"
    items = json.loads(ledger.read_text()).get(slug, []) if ledger.exists() else []
    normalize = lambda value: re.sub(r"\s+", " ", unescape(value)).casefold().strip()

    class Text(HTMLParser):
        def __init__(self):
            super().__init__()
            self.parts = []

        def handle_data(self, data):
            self.parts.append(data)

    sources = {}
    for name in ["concept.json", "index.html", "demo.html"]:
        path = workspace / "site/entries" / slug / name
        if not path.is_file():
            continue  # The static validator reports missing files separately.
        parser = Text()
        parser.feed(path.read_text())
        sources[f"site/entries/{slug}/{name}"] = normalize(" ".join(parser.parts))
    checks = []
    for item in items:
        matches = [{"file": name, "quote": phrase}
                   for phrase in item["rejected_phrases"] for name, source in sources.items()
                   if normalize(phrase) in source]
        checks.append({"id": item["id"], "reason": item["reason"], "matches": matches})
    return {"passed": all(not item["matches"] for item in checks), "checks": checks}


def object_schema(properties):
    return {"type": "object", "properties": properties, "required": list(properties), "additionalProperties": False}


TEXT = {"type": "string", "minLength": 1}
# Input values and exact-value expectations may legitimately be empty (for
# example, a composer clearing its text box after submission).
VALUE = {"type": "string", "minLength": 0}
REVIEW_SCHEMA = object_schema({
    "slug": TEXT,
    "verdict": {"type": "string", "enum": ["pass", "repair"]},
    "premise": TEXT,
    "strengths": {"type": "array", "items": TEXT},
    "findings": {"type": "array", "items": object_schema({
        "category": {"type": "string", "enum": ["satire", "consistency", "ux", "runtime"]},
        "file": TEXT, "quote": TEXT, "problem": TEXT, "fix": TEXT,
    })},
    "demo_test": object_schema({
        "actions": {"type": "array", "items": object_schema({
            "action": {"type": "string", "enum": ["click", "fill", "select", "press"]},
            "selector": TEXT, "value": VALUE,
        })},
        "assertions": {"type": "array", "items": object_schema({
            "check": {"type": "string", "enum": ["visible", "hidden", "text", "count", "value"]},
            "selector": TEXT, "expected": VALUE,
        })},
    }),
})


def validate_shape(value, schema):
    """Validate this small schema locally too; never trust a completion alone."""
    kind = schema["type"]
    if kind == "object":
        if not isinstance(value, dict) or set(value) != set(schema["properties"]):
            raise ValueError("QA report has missing or unexpected fields")
        for key, rule in schema["properties"].items():
            validate_shape(value[key], rule)
    elif kind == "array":
        if not isinstance(value, list):
            raise ValueError("QA report field must be an array")
        for item in value:
            validate_shape(item, schema["items"])
    elif kind == "string":
        if not isinstance(value, str) or (schema.get("minLength", 1) > 0 and not value.strip()):
            raise ValueError("QA report text must be nonempty")
    elif kind == "boolean" and type(value) is not bool:
        raise ValueError("QA report pass flags must be booleans")
    if "enum" in schema and value not in schema["enum"]:
        raise ValueError("Invalid QA report verdict or category")


def read_review(path, slug):
    report = json.loads(path.read_text())
    validate_shape(report, review_schema(slug))
    if report["slug"] != slug:
        raise ValueError("QA reviewed the wrong entry")
    if any(not 1 <= len(report["demo_test"][key]) <= 8 for key in ["actions", "assertions"]):
        raise ValueError("QA requires a bounded executable demo interaction test")
    for action in report["demo_test"]["actions"]:
        if action["action"] == "press" and not action["value"].strip():
            raise ValueError("QA press action requires a key")
    for assertion in report["demo_test"]["assertions"]:
        if assertion["check"] == "text" and not assertion["expected"].strip():
            raise ValueError("QA text assertion requires a nonempty substring")
        if assertion["check"] == "count" and not re.fullmatch(r"[0-9]+", assertion["expected"]):
            raise ValueError("QA count assertion requires a nonnegative integer")
    if report["verdict"] == "pass" and report["findings"]:
        raise ValueError("QA pass contradicts its findings")
    if report["verdict"] == "repair" and not report["findings"]:
        raise ValueError("QA requested repair without actionable findings")
    return report


def review_schema(slug):
    schema = json.loads(json.dumps(REVIEW_SCHEMA))
    schema["properties"]["findings"]["items"]["properties"]["file"]["enum"] = [
        f"site/entries/{slug}/{name}" for name in ["concept.json", "index.html", "demo.html"]
    ] + ["site/index.html"]
    return schema


def guarded_files(workspace, slug):
    """Snapshot critical content outside the repair allowlist, including assets."""
    allowed = {f"site/entries/{slug}/{name}" for name in ["concept.json", "index.html", "demo.html"]} | {"site/index.html"}
    paths = [workspace / name for name in ["pipeline.md", "CLAUDE.md", "README.md", "state/history.json"]]
    for name in ["site", "scripts", "pipelines", "seeds"]:
        root = workspace / name
        if root.exists():
            paths.extend(path for path in root.rglob("*") if path.is_file() and "__pycache__" not in path.parts)
    return {str(path.relative_to(workspace)): path.read_bytes() for path in paths
            if path.is_file() and str(path.relative_to(workspace)) not in allowed}


def enforce_scope(workspace, slug, before):
    after = guarded_files(workspace, slug)
    changed = {name for name in before.keys() | after.keys() if before.get(name) != after.get(name)}
    if changed:
        for name in changed:
            path = workspace / name
            if name in before:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(before[name])
            else:
                path.unlink(missing_ok=True)
        raise StageFailure("QA repair changed protected content; changes restored and publication refused")


def run_qa(workspace, slug, config, run, invoke, deadline):
    """invoke(prompt, label, timeout, read_only=False, schema=None) -> final file."""
    qa = config["qa"]
    bundle = workspace / "pipelines/codex-v1"
    entry = entry_path(workspace, slug)
    original = json.loads((entry / "concept.json").read_text())
    identity = {key: original[key] for key in ["date", "company", "subject", "slug", "product_name", "design_direction"]}
    if original["slug"] != slug:
        raise ValueError("QA target concept has the wrong slug")
    shutil.copytree(entry, run / "draft-before-qa")
    schema = run / "qa-schema.json"
    schema.write_text(json.dumps(review_schema(slug), indent=2) + "\n")
    summary = {"slug": slug, "status": "failed", "repair_attempts": 0, "reviews": []}
    summary_path = run / "qa-summary.json"
    try:
        for attempt in range(qa["max_repair_attempts"] + 1):
            with preview(workspace) as base:
                directory = run / f"checks-{attempt}"
                technical = technical_checks(workspace, slug, directory, base, qa, deadline)
                context = {"slug": slug, "entry_directory": str(entry), "preview_url": base,
                           "technical_report": str(directory / "technical.json"),
                           "browser_report": str(directory / "browser.json"),
                           "review_number": attempt, "previous_review": summary["reviews"][-1] if summary["reviews"] else None,
                           "all_previous_reviews": summary["reviews"].copy(),
                           "previous_checks": str(run / f"checks-{attempt - 1}" / "technical.json") if attempt else None}
                prompt = (bundle / "qa.md").read_text() + "\n\nHOST REVIEW CONTEXT:\n" + json.dumps(context, indent=2)
                print(f"codex QA: review {attempt + 1}, repairs used {attempt}/{qa['max_repair_attempts']}", flush=True)
                report_path = invoke(prompt, f"review-{attempt}", budget(deadline, qa["review_timeout_seconds"]),
                                     read_only=True, schema=schema)
                report = read_review(report_path, slug)
                summary["reviews"].append(str(report_path))
                interaction_log = directory / "interaction.log"
                code = execute(["node", "scripts/check-entry-browser.cjs", "--interaction", base, slug,
                                str(report_path), str(directory)], workspace, interaction_log,
                               budget(deadline, qa["browser_timeout_seconds"]))
                technical["checks"].append({"name": "interaction", "passed": code == 0,
                                            "log": str(interaction_log), "report": str(directory / "interaction.json")})
                technical["passed"] = all(check["passed"] for check in technical["checks"])
                (directory / "technical.json").write_text(json.dumps(technical, indent=2) + "\n")
            if technical["passed"] and report["verdict"] == "pass":
                summary["status"] = "passed"
                print(f"codex QA: passed after {attempt} repair attempt(s)", flush=True)
                return summary
            if attempt == qa["max_repair_attempts"]:
                raise StageFailure(f"QA failed after {attempt} repair attempts; refusing publication; private reports: {run}")
            context = {"slug": slug, "review": str(report_path), "technical_report": str(directory / "technical.json"),
                       "browser_report": str(directory / "browser.json"), "attempt": attempt + 1,
                       "all_previous_reviews": summary["reviews"].copy()}
            prompt = (bundle / "heal.md").read_text() + "\n\nHOST REPAIR CONTEXT:\n" + json.dumps(context, indent=2)
            before = guarded_files(workspace, slug)
            summary["repair_attempts"] = attempt + 1
            try:
                invoke(prompt, f"repair-{attempt + 1}", budget(deadline, qa["repair_timeout_seconds"]))
            finally:
                enforce_scope(workspace, slug, before)
            updated = json.loads((entry / "concept.json").read_text())
            if any(updated.get(key) != value for key, value in identity.items()):
                raise StageFailure("QA repair changed product identity or design direction; refusing publication")
    finally:
        summary_path.write_text(json.dumps(summary, indent=2) + "\n")
