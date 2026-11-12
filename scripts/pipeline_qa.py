"""Host-controlled QA with a shared repair allowance and a final publish decision."""

from contextlib import contextmanager
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
import hashlib
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


QUALITY_FLOOR_ID = "again-2026-11-11-approved"


def design_guidance_context(workspace, stage):
    """Read only reviewed local text; never install or execute upstream tooling."""
    selections = {
        "concept": ("GUIDE.md",),
        "build": ("GUIDE.md", "references/adapt.md", "references/harden.md"),
        "review": ("GUIDE.md", "references/critique.md", "references/audit.md"),
        "repair": ("GUIDE.md", "references/adapt.md", "references/harden.md"),
    }
    names = {name for selection in selections.values() for name in selection} | {"LICENSE", "NOTICE.md"}
    root = workspace / "pipelines/codex-v1/design-guidance/impeccable"
    paths = list(root.rglob("*"))
    if (not root.resolve().is_relative_to(workspace.resolve()) or root.is_symlink()
            or any(path.is_symlink() for path in paths)):
        raise ValueError("Design guidance must contain regular local text, not symlinks")
    actual = {str(path.relative_to(root)) for path in paths if path.is_file()}
    if actual != names | {"SOURCE.json"} or any(path.stat().st_mode & 0o111 for path in paths if path.is_file()):
        raise ValueError("Design guidance must contain only its reviewed nonexecutable text files")
    manifest = json.loads((root / "SOURCE.json").read_text())
    if (not isinstance(manifest, dict) or manifest.get("format") != 1 or manifest.get("kind") != "text-only"
            or manifest.get("upstream_repository") != "https://github.com/pbakaus/impeccable"
            or manifest.get("upstream_commit") != "b4bff1626c344067788c2679f048a20057c7cc5a"
            or not isinstance(manifest.get("files"), dict) or set(manifest["files"]) != names):
        raise ValueError("Invalid pinned design guidance provenance")
    documents = {}
    for name in sorted(names):
        data = (root / name).read_bytes()
        if hashlib.sha256(data).hexdigest() != manifest["files"][name]:
            raise ValueError(f"Reviewed design guidance missing or changed: {name}")
        documents[name] = data.decode("utf-8")
    return {"upstream_commit": manifest["upstream_commit"], "kind": "local text-only adaptation",
            "documents": [{"file": name, "text": documents[name]} for name in selections[stage]]}


def quality_floor_context(workspace):
    """Pinned human approval survives catalogue rotation and later entry edits."""
    path = workspace / "pipelines/codex-v1/quality-floor.json"
    floor = json.loads(path.read_text())
    if floor.get("id") != QUALITY_FLOOR_ID or set(floor.get("criteria", {})) != {
            "comprehension", "satire", "composition", "continuity"}:
        raise ValueError("Invalid approved quality floor")
    if not all(isinstance(value, str) and value.strip() for value in floor["criteria"].values()):
        raise ValueError("Quality floor criteria must be nonempty")
    refs = floor.get("reference_images", [])
    if not isinstance(refs, list) or len(refs) != 3:
        raise ValueError("Quality floor needs its three approved reference captures")
    images = []
    for reference in refs:
        image = workspace / reference["file"]
        if not image.resolve().is_relative_to((workspace / "pipelines/codex-v1/reference").resolve()):
            raise ValueError("Quality floor image must stay inside the reference directory")
        if not image.is_file() or hashlib.sha256(image.read_bytes()).hexdigest() != reference["sha256"]:
            raise ValueError("Approved quality floor image missing or changed")
        images.append(image)
    if len(set(images)) != 3:
        raise ValueError("Quality floor captures must be distinct")
    return floor, images


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
    quality_floor_context(workspace)
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
    if "verification_timeout_seconds" in qa:
        value = qa["verification_timeout_seconds"]
        if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
            raise ValueError("QA verification_timeout_seconds must be positive")
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
FINDING = object_schema({
    "id": TEXT, "target": TEXT, "acceptance": TEXT,
    "category": {"type": "string", "enum": ["satire", "consistency", "ux", "runtime"]},
    "file": TEXT, "quote": TEXT, "problem": TEXT, "fix": TEXT,
    # Empty old means an instruction-based repair. Nonempty old is a unique,
    # literal source match; the host applies a batch only when every edit matches.
    "patch": object_schema({"old": VALUE, "new": VALUE}),
})
REVIEW_SCHEMA = object_schema({
    "slug": TEXT,
    "verdict": {"type": "string", "enum": ["pass", "repair"]},
    "premise": TEXT,
    "strengths": {"type": "array", "items": TEXT},
    "checks": object_schema({name: {"type": "boolean"} for name in
                             ["comprehension", "satire", "composition", "continuity"]}),
    "quality_floor": object_schema({
        "reference_id": {"type": "string", "enum": [QUALITY_FLOOR_ID]},
        "assessments": object_schema({name: object_schema({"meets": {"type": "boolean"}, "evidence": TEXT})
                                      for name in ["comprehension", "satire", "composition", "continuity"]}),
    }),
    "copy_audit": {"type": "array", "items": object_schema({
        "target": TEXT, "behavior": TEXT, "mechanic": TEXT, "connection": TEXT,
    })},
    "visual_audit": {"type": "array", "items": object_schema({
        "page": {"type": "string", "enum": ["index.html", "demo.html"]},
        "viewport": {"type": "string", "enum": ["desktop", "mobile"]},
        "dominant_content": TEXT, "product_visual": TEXT, "caption_legibility": TEXT,
        "comprehension_pass": {"type": "boolean"},
        "audience_cues": TEXT, "audience_fit_pass": {"type": "boolean"},
    })},
    "resolved_findings": {"type": "array", "items": TEXT},
    "findings": {"type": "array", "items": FINDING},
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
        if len(value) < schema.get("minItems", 0) or len(value) > schema.get("maxItems", math.inf):
            raise ValueError("QA report array has invalid length")
    elif kind == "string":
        if not isinstance(value, str) or (schema.get("minLength", 1) > 0 and not value.strip()):
            raise ValueError("QA report text must be nonempty")
    elif kind == "boolean" and type(value) is not bool:
        raise ValueError("QA report pass flags must be booleans")
    if "enum" in schema and value not in schema["enum"]:
        raise ValueError("Invalid QA report verdict or category")


def validate_verdict(report, previous_ids=()):
    ids = [finding["id"] for finding in report["findings"]]
    if len(ids) != len(set(ids)):
        raise ValueError("QA finding IDs must be unique")
    if report["verdict"] == "pass" and (ids or not all(report["checks"].values())):
        raise ValueError("QA pass contradicts findings or acceptance checks")
    floor = report.get("quality_floor")
    if floor and report["verdict"] == "pass" and not all(item["meets"] for item in floor["assessments"].values()):
        raise ValueError("QA pass falls below the user-approved quality floor")
    if report["verdict"] == "repair" and not ids:
        raise ValueError("QA requested repair without actionable findings")
    if not set(previous_ids) <= set(ids) | set(report["resolved_findings"]):
        raise ValueError("QA omitted an earlier finding without verifying resolution")
    if set(ids) & set(report["resolved_findings"]):
        raise ValueError("QA finding cannot be both unresolved and resolved")


def validate_copy_audit(report, concept):
    expected = {f"features.{i}" for i, _ in enumerate(concept.get("features", []))}
    expected |= {f"pricing_tiers.{i}.perks.{j}" for i, tier in enumerate(concept.get("pricing_tiers", []))
                 for j, _ in enumerate(tier.get("perks", []))}
    if not expected <= {item["target"] for item in report["copy_audit"]}:
        raise ValueError("QA copy audit omitted a feature or pricing perk")


def validate_visual_audit(report):
    expected = {(page, viewport) for page in ("index.html", "demo.html") for viewport in ("desktop", "mobile")}
    if expected != {(item["page"], item["viewport"]) for item in report["visual_audit"]}:
        raise ValueError("QA visual audit must cover both pages on desktop and mobile")
    if report["checks"]["composition"] and not all(item["comprehension_pass"] for item in report["visual_audit"]):
        raise ValueError("Composition pass contradicts visual observations")
    if report["checks"]["composition"] and not all(item.get("audience_fit_pass", False) for item in report["visual_audit"]):
        raise ValueError("Composition pass contradicts audience fit observations")


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
    validate_verdict(report)
    validate_visual_audit(report)
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


class RepairAllowance:
    def __init__(self, limit, run):
        self.limit, self.run, self.used = limit, run, 0

    def claim(self, stage):
        if self.used >= self.limit:
            raise StageFailure(f"QA failed after {self.used} repair attempts; refusing publication")
        self.used += 1
        path = self.run / "repair-budget.json"
        records = json.loads(path.read_text()) if path.exists() else []
        records.append({"attempt": self.used, "stage": stage})
        path.write_text(json.dumps(records, indent=2) + "\n")
        return self.used


def apply_exact_patches(workspace, slug, findings):
    """Apply an entirely literal batch atomically after validating all matches."""
    if not findings or any(not item["patch"]["old"] for item in findings):
        return False
    allowed = {f"site/entries/{slug}/{name}" for name in ["concept.json", "index.html", "demo.html"]}
    staged = {}
    for item in findings:
        name, patch = item["file"], item["patch"]
        path = workspace / name
        if name not in allowed or path.is_symlink():
            return False
        source = staged.get(name, path.read_text())
        if source.count(patch["old"]) != 1 or patch["old"] == patch["new"]:
            return False
        staged[name] = source.replace(patch["old"], patch["new"], 1)
    for name, source in staged.items():
        if name.endswith("concept.json"):
            json.loads(source)
    for name, source in staged.items():
        (workspace / name).write_text(source)
    return True


def review_packet(workspace, slug, directory):
    """Extract copy once; keep styling, duplicated metadata and traces out of QA."""
    class Page(HTMLParser):
        def __init__(self):
            super().__init__()
            self.skip = 0
            self.script = False
            self.copy, self.scripts, self.images, self.links = [], [], [], []

        def handle_starttag(self, tag, attrs):
            attrs = dict(attrs)
            if tag in ("head", "style", "script"):
                self.skip += 1
            self.script = tag == "script" or self.script
            if tag == "img":
                self.images.append({key: attrs.get(key, "") for key in ("src", "alt")})
            if tag == "a":
                self.links.append(attrs.get("href", ""))
            if not self.skip and tag in ("h1", "h2", "h3", "button", "input", "select", "textarea"):
                self.copy.append(f"<{tag} id={attrs.get('id', '')!r} label={attrs.get('aria-label', '')!r}>")

        def handle_endtag(self, tag):
            if tag in ("head", "style", "script"):
                self.skip -= 1
            if tag == "script":
                self.script = False

        def handle_data(self, data):
            if self.script:
                self.scripts.append(data)
            elif not self.skip and data.strip():
                self.copy.append(data.strip())

    pages = {}
    for name in ("index.html", "demo.html"):
        source = workspace / "site/entries" / slug / name
        if not source.is_file():
            pages[name] = {"error": "Missing page; see static checks"}
            continue
        page = Page()
        page.feed(source.read_text())
        pages[name] = {"copy": page.copy, "images": page.images, "links": page.links}
        if name == "demo.html":
            pages[name]["scripts"] = page.scripts
    path = directory / "review-packet.json"
    path.write_text(json.dumps(pages, indent=2, ensure_ascii=False) + "\n")
    return path


def final_review_input(workspace, slug, directory, context):
    """Attach evidence and inline compact inputs so reviews need no file rereads."""
    browser = json.loads((directory / "browser.json").read_text())
    images, labels = [], []
    coverage = set()
    for page in browser.get("pages", []):
        viewport = "mobile" if page["viewport"]["width"] < 700 else "desktop"
        coverage.add((page["filename"], page["viewport"]["width"]))
        fields = ("foldScreenshot", "screenshot") if page["filename"] == "index.html" else ("screenshot",)
        for field in fields:
            name = page.get(field)
            if not name or not Path(name).is_file():
                raise StageFailure("Missing screenshot attachment; refusing an ungrounded visual review")
            images.append(Path(name))
            labels.append({"image": len(images), "page": page["filename"], "viewport": viewport,
                           "width": page["viewport"]["width"],
                           "capture": "opening" if field == "foldScreenshot" else "full page"})
    if coverage != {(page, width) for page in ("index.html", "demo.html") for width in (1440, 390, 320)}:
        raise StageFailure("Missing required desktop/mobile viewport captures; refusing visual review")
    floor, reference_images = quality_floor_context(workspace)
    for reference, image in zip(floor["reference_images"], reference_images):
        images.append(image)
        labels.append({"image": len(images), "quality_reference": floor["id"],
                       "capture": reference["purpose"]})
    concept = json.loads((workspace / "site/entries" / slug / "concept.json").read_text())
    compact = {key: value for key, value in concept.items() if key != "images"}
    compact["image_provenance"] = [{key: item.get(key) for key in ("file", "role", "source", "source_file", "transformation")}
                                   for item in concept.get("images", {}).get("items", [])]
    previous = [json.loads(Path(path).read_text()) for path in context.get("all_previous_reviews", [])]
    data = {**context, "attached_images": labels, "approved_quality_floor": floor,
            "design_guidance": design_guidance_context(workspace, "review"),
            "page_content": json.loads((directory / "review-packet.json").read_text()),
            "concept_after_page_review": compact,
            "technical_checks": json.loads((directory / "technical.json").read_text()),
            "human_feedback": json.loads((directory / "editorial-regressions.json").read_text()),
            "browser_failures": browser.get("failures", []),
            "browser_findings": [{key: page.get(key) for key in ("filename", "viewport", "failures", "errors", "brokenImages")}
                                 for page in browser["pages"]],
            "previous_findings": [{"findings": report["findings"], "resolved_findings": report["resolved_findings"]}
                                  for report in previous]}
    return data, images


def run_qa(workspace, slug, config, run, invoke, deadline, allowance=None):
    """invoke(prompt, label, timeout, read_only=False, schema=None) -> final file."""
    qa = config["qa"]
    allowance = allowance or RepairAllowance(qa["max_repair_attempts"], run)
    bundle = workspace / "pipelines/codex-v1"
    entry = entry_path(workspace, slug)
    original = json.loads((entry / "concept.json").read_text())
    identity = {key: original[key] for key in ["date", "company", "subject", "slug", "product_name", "design_direction"]}
    if original["slug"] != slug:
        raise ValueError("QA target concept has the wrong slug")
    shutil.copytree(entry, run / "draft-before-qa")
    schema = run / "qa-schema.json"
    schema.write_text(json.dumps(review_schema(slug), indent=2) + "\n")
    summary = {"slug": slug, "status": "failed", "repair_attempts": allowance.used, "reviews": []}
    summary_path = run / "qa-summary.json"
    try:
        previous_ids = set()
        for attempt in range(qa["max_repair_attempts"] + 1):
            with preview(workspace) as base:
                directory = run / f"checks-{attempt}"
                technical = technical_checks(workspace, slug, directory, base, qa, deadline)
                packet = review_packet(workspace, slug, directory)
                context = {"slug": slug, "entry_directory": str(entry), "preview_url": base,
                           "review_packet": str(packet),
                           "approved_concept": str(run / "approved-concept.json") if (run / "approved-concept.json").exists() else None,
                           "technical_report": str(directory / "technical.json"),
                           "browser_report": str(directory / "browser.json"),
                           "review_number": attempt, "previous_review": summary["reviews"][-1] if summary["reviews"] else None,
                           "all_previous_reviews": summary["reviews"].copy(),
                           "previous_checks": str(run / f"checks-{attempt - 1}" / "technical.json") if attempt else None}
                context, images = final_review_input(workspace, slug, directory, context)
                prompt = (bundle / "qa.md").read_text() + "\n\nHOST REVIEW CONTEXT:\n" + json.dumps(context, indent=2)
                print(f"codex QA: review {attempt + 1}, repairs used {allowance.used}/{allowance.limit}", flush=True)
                review_limit = qa.get("verification_timeout_seconds", qa["review_timeout_seconds"]) if attempt else qa["review_timeout_seconds"]
                report_path = invoke(prompt, f"review-{attempt}", budget(deadline, review_limit),
                                     read_only=True, schema=schema, images=images)
                report = read_review(report_path, slug)
                validate_verdict(report, previous_ids)
                validate_copy_audit(report, json.loads((entry / "concept.json").read_text()))
                previous_ids |= {finding["id"] for finding in report["findings"]}
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
                print(f"codex QA: passed after {allowance.used} repair attempt(s)", flush=True)
                return summary
            number = allowance.claim("final")
            context = {"slug": slug, "review": str(report_path), "technical_report": str(directory / "technical.json"),
                       "browser_report": str(directory / "browser.json"), "attempt": number,
                       "all_previous_reviews": summary["reviews"].copy(),
                       "approved_quality_floor": quality_floor_context(workspace)[0]}
            context["design_guidance"] = design_guidance_context(workspace, "repair")
            prompt = (bundle / "heal.md").read_text() + "\n\nHOST REPAIR CONTEXT:\n" + json.dumps(context, indent=2)
            before = guarded_files(workspace, slug)
            summary["repair_attempts"] = allowance.used
            try:
                patched = technical["passed"] and apply_exact_patches(workspace, slug, report["findings"])
                if not patched:
                    invoke(prompt, f"repair-{number}", budget(deadline, qa["repair_timeout_seconds"]))
            finally:
                enforce_scope(workspace, slug, before)
            updated = json.loads((entry / "concept.json").read_text())
            if any(updated.get(key) != value for key, value in identity.items()):
                raise StageFailure("QA repair changed product identity or design direction; refusing publication")
    finally:
        summary_path.write_text(json.dumps(summary, indent=2) + "\n")
