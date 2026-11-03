#!/usr/bin/env python3
"""Rebuild an existing entry with Codex in isolation; never publish or notify."""

import argparse
from datetime import datetime, timezone
import html
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import tempfile
import time


ROOT = Path(__file__).resolve().parent.parent
QUALITY_REVISION = 2


def skill_source(name):
    for base in [ROOT / "prompts/skills", ROOT / ".agents/skills", Path.home() / ".agents/skills",
                 Path.home() / ".codex/skills", Path.home() / ".claude/skills"]:
        candidate = base / name
        if (candidate / "SKILL.md").is_file():
            return candidate
    marketplace = Path.home() / ".claude/plugins/marketplaces"
    matches = sorted(marketplace.glob(f"*/**/skills/{name}/SKILL.md"))
    if matches:
        return matches[0].parent
    raise SystemExit(f"Missing required skill: {name}. Install it before running a trial.")


def prepare(entry):
    baseline = ROOT / "site/entries" / entry
    if not (baseline / "concept.json").is_file():
        raise SystemExit(f"No existing entry: {entry}")
    concept = json.loads((baseline / "concept.json").read_text())
    if concept.get("slug") != entry:
        raise SystemExit("Entry directory and concept slug disagree")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    output = ROOT / "_test/codex-comparison" / f"{stamp}-{entry}"
    output.mkdir(parents=True)
    workspace = Path(tempfile.mkdtemp(prefix="worst-codex-trial-"))
    for directory in ["seeds", "state/runs", "site/entries", ".agents/skills"]:
        (workspace / directory).mkdir(parents=True)
    sources = {}
    snapshot = output / "baseline"
    shutil.copytree(baseline, snapshot)
    for name in ["anti-ai-slop", "frontend-design", "ui-ux-pro-max", "frontend-skill"]:
        source = skill_source(name)
        sources[name] = str(source)
        # Dereference symlinks: ui-ux-pro-max's data and scripts live elsewhere
        # in its plugin. Copy the resources too, so the trial is self-contained.
        shutil.copytree(source, workspace / ".agents/skills" / name,
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    shutil.copytree(ROOT / "scripts", workspace / "scripts",
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    shutil.copy2(ROOT / "pipeline.md", workspace / "pipeline.md")
    shutil.copy2(ROOT / "prompts/codex-quality.md", workspace / "codex-quality.md")
    for filename in ["styles.css", "404.html", "CNAME", "favicon.png", "logo.png"]:
        shutil.copy2(ROOT / "site" / filename, workspace / "site" / filename)
    for field, filename in [("company", "companies.json"), ("subject", "subjects.json")]:
        (workspace / "seeds" / filename).write_text(json.dumps([concept[field]]) + "\n")
    # Supply the same historical design context, without the baseline's copy,
    # HTML, or design direction. The agent must compose its own implementation.
    previous = []
    for path in (ROOT / "site/entries").glob("*/concept.json"):
        data = json.loads(path.read_text())
        if data["date"] < concept["date"]:
            previous.append((data["date"], path))
    history = []
    for _, path in sorted(previous, reverse=True)[:7]:
        target = workspace / "site/entries" / path.parent.name
        target.mkdir()
        shutil.copy2(path, target / "concept.json")
        data = json.loads(path.read_text())
        history.append({key: data[key] for key in ["date", "company", "subject", "slug"]})
    (workspace / "state/history.json").write_text(json.dumps(history, indent=2) + "\n")
    target = workspace / "site/entries" / entry
    target.mkdir()
    images = []
    for path in baseline.iterdir():
        if path.suffix.lower() in {".png", ".webp", ".jpeg", ".jpg", ".gif"} and path.name != "social-preview.jpg":
            shutil.copy2(path, target / path.name)
            images.append(path.name)
    brief = {key: concept[key] for key in ["date", "company", "subject", "slug", "tagline", "product_name", "demo_screen_concept"]}
    requirements = ROOT / "prompts/comparisons" / f"{entry}.json"
    if requirements.is_file():
        brief["comparison_requirements"] = json.loads(requirements.read_text())
    (workspace / "trial-brief.json").write_text(json.dumps(brief, indent=2) + "\n")
    instructions = """This directory is an isolated Codex comparison trial.
Read pipeline.md and execute it using the trial overrides below. Do not delegate.
Do not use connected apps, publishing services, git, Telegram, or deployment tools.
Do not read or write outside this workspace. Never read the original repository.
Never read authentication files, .env files, or invoke another coding agent.
Use local shell/file tools to read and apply these skills before their relevant steps:
.agents/skills/anti-ai-slop/SKILL.md
.agents/skills/ui-ux-pro-max/SKILL.md
.agents/skills/frontend-design/SKILL.md
.agents/skills/frontend-skill/SKILL.md
Reading and following these files satisfies the prompt's Claude Skill invocations.
Skill examples that ask for package installation yield to the pipeline's no-install rule.
Read codex-quality.md before planning or writing copy. Its quality contract and
trial-brief.json's comparison_requirements override generic skill defaults.
Both quality-plan.json and quality-review.json are required host-checked artifacts.

Trial overrides take precedence over pipeline.md:
1. trial-brief.json fixes the company, subject, slug, product name, original date,
   and demo premise. Skip the random roll. Preserve this product and its core
   demo behaviors; write new hero copy, feature copy, pricing, and testimonials.
   Keep testimonial names consistent with the supplied headshot subjects.
2. Choose your own visual direction using the prior seven concepts. Do not
   imitate an existing page. The original entry's HTML and copy are unavailable.
3. Replace image generation with the already supplied image files in the entry
   directory. Use them where appropriate; no image API calls. Record that assets
   were reused for a controlled comparison, not generated by Codex. Do not invent
   image prompts, generation counts, or vision-review results.
4. The date in concept.json stays fixed to the trial brief. Append only to this
   workspace's history. All output and scratch files stay inside this directory.
5. Complete metadata generation and validation. Skip Step 9 screenshot capture:
   the host will perform the same desktop/mobile browser checks on both versions.
   Do not install software or run a browser/server yourself.
6. This run has a host-enforced time limit, rather than Claude's 80-turn cap.
   Finish the landing page, interactive demo, concept, and validation first.
7. Finish with RUN_COMPLETE: <slug>. If validation fails, explain the failure
   and do not print RUN_COMPLETE. Do not claim screenshots or interaction tests.
"""
    (workspace / "AGENTS.md").write_text(instructions)
    (output / "manifest.json").write_text(json.dumps({
        "entry": entry, "workspace": str(workspace), "baseline": str(snapshot),
        "baseline_source": str(baseline),
        "skills": sources, "shared_images": images, "status": "prepared",
        "quality_revision": QUALITY_REVISION,
        "model": "Uses the installed Codex CLI configuration; see codex.log for resolved model.",
        "comparison": "Existing Claude output versus one Codex rebuild; same product brief and image assets. This is not a blinded or multi-sample benchmark.",
    }, indent=2) + "\n")
    return output


def finish(output, manifest):
    workspace = Path(manifest["workspace"])
    entry = manifest["entry"]
    if manifest.get("quality_revision", 1) >= 2:
        for name, fields in {
            "quality-plan.json": ["source_product_patterns", "primary_workflow", "landing_direction", "demo_direction", "satire_observations", "headline_candidates", "selected_headline"],
            "quality-review.json": ["source_fidelity", "landing_composition", "satire", "mobile_plan", "limits"],
        }.items():
            path = workspace / name
            if not path.is_file():
                raise RuntimeError(f"Missing quality checkpoint: {name}")
            data = json.loads(path.read_text())
            if not isinstance(data, dict) or any(not data.get(field) for field in fields):
                raise RuntimeError(f"Incomplete quality checkpoint: {name}")
            if name == "quality-plan.json":
                for field, minimum in [("source_product_patterns", 4), ("satire_observations", 3), ("headline_candidates", 3)]:
                    if not isinstance(data[field], list) or len(data[field]) < minimum:
                        raise RuntimeError(f"Quality checkpoint needs at least {minimum} {field}")
            shutil.copy2(path, output / name)
    for command in [["python3", "scripts/build-entry-metadata.py", "site", entry],
                    ["bash", "scripts/validate-entry.sh", "site", entry]]:
        subprocess.run(command, cwd=workspace, check=True)
    generated = json.loads((workspace / "site/entries" / entry / "concept.json").read_text())
    brief = json.loads((workspace / "trial-brief.json").read_text())
    for key in ["date", "company", "subject", "slug", "tagline", "product_name"]:
        if generated[key] != brief[key]:
            raise RuntimeError(f"Generated entry changed fixed brief field: {key}")
    if not any(line.strip() == f"RUN_COMPLETE: {entry}" for line in (output / manifest.get("result_file", "result.txt")).read_text().splitlines()):
        raise RuntimeError("Codex did not report RUN_COMPLETE")
    public = output / "public"
    for label, source in [("claude", Path(manifest["baseline"])),
                          ("codex", workspace / "site/entries" / entry)]:
        shutil.copytree(source, public / label / "entries" / entry,
                        dirs_exist_ok=bool(manifest.get("repair_count")))
    title = html.escape(brief["tagline"])
    public.joinpath("index.html").write_text(f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Claude and Codex comparison: {title}</title><style>
*{{box-sizing:border-box}}body{{font:17px/1.5 system-ui,sans-serif;max-width:1000px;margin:0 auto;padding:40px 24px;background:#f5f5f5;color:#202020}}
h1{{font-size:clamp(28px,5vw,44px);line-height:1.12}}.versions{{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:20px;margin:32px 0}}
article{{background:white;padding:24px;border:1px solid #ccc;border-radius:12px}}a{{color:#234cb0}}a:focus-visible{{outline:3px solid #234cb0;outline-offset:4px}}
article a{{display:block;margin:14px 0}}li{{margin:8px 0}}small{{color:#555}}</style></head><body>
<h1>{title}</h1><p>The same product, rebuilt with Codex. Both versions use the same photographs.</p>
<div class="versions"><article><h2>Claude original</h2><a href="claude/entries/{entry}/">Open landing page</a>
<a href="claude/entries/{entry}/demo.html">Open interactive demo</a></article><article><h2>Codex rebuild</h2>
<a href="codex/entries/{entry}/">Open landing page</a><a href="codex/entries/{entry}/demo.html">Open interactive demo</a></article></div>
<p>Compare each version on your phone and desktop:</p><ul><li>Visual identity, typography, spacing, and ease of reading.</li>
<li>Satire: specific observations, deadpan delivery, and whether the joke holds across the page.</li>
<li>Demo: search, filters, editing, and whether actions produce a useful response.</li></ul>
<small>One trial, with model labels visible. The original is a snapshot of the local Claude output.
This preview does not publish either entry or change the daily job.</small></body></html>""")
    manifest["status"] = "validated"
    manifest["public"] = str(public)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--entry", default="notion-for-wedding-djs")
    parser.add_argument("--prepare-only", action="store_true")
    parser.add_argument("--prepared", type=Path, help="Run a previously prepared trial directory")
    parser.add_argument("--repair", type=Path, help="Repair one validated trial from host feedback; at most once")
    parser.add_argument("--feedback", type=Path, help="Text file describing browser-verified defects for --repair")
    parser.add_argument("--timeout", type=int, default=1200, help="Codex time limit in seconds")
    args = parser.parse_args()
    if args.repair and (args.prepared or args.prepare_only or not args.feedback):
        parser.error("--repair requires --feedback and cannot be combined with preparation options")
    if args.feedback and not args.repair:
        parser.error("--feedback requires --repair")
    if not shutil.which("codex"):
        raise SystemExit("codex is not on PATH; install and sign in before running a trial")
    if Path(args.entry).name != args.entry or args.entry in {".", ".."}:
        parser.error("--entry must be an entry directory name")
    output = (args.repair or args.prepared).resolve() if (args.repair or args.prepared) else prepare(args.entry)
    print(f"Trial: {output}", flush=True)
    if args.prepare_only:
        return
    manifest = json.loads((output / "manifest.json").read_text())
    workspace = Path(manifest["workspace"])
    if args.repair:
        if manifest["status"] != "validated" or manifest.get("repair_count", 0):
            raise SystemExit("Repair requires a validated trial with no previous repair pass")
        shutil.copy2(args.feedback, workspace / "host-feedback.txt")
        shutil.copy2(args.feedback, output / "host-feedback.txt")
        shutil.copy2(ROOT / "prompts/codex-quality.md", workspace / "codex-quality.md")
        manifest["repair_count"] = 1
        manifest["result_file"] = "repair-result.txt"
        prompt = "Read AGENTS.md, codex-quality.md and host-feedback.txt. Make one bounded repair of the reported defects in this existing entry. Preserve unrelated design, copy, image files and history. Update quality-review.json with the repair, rerun metadata and validation, and finish with RUN_COMPLETE: " + manifest["entry"]
    else:
        if manifest["status"] != "prepared":
            raise SystemExit("This trial has already run; prepare a new trial instead")
        prompt = "Read AGENTS.md, codex-quality.md and trial-brief.json. Apply all four design/writing skills. Plan the source-product UX and satire, then execute pipeline.md with the trial overrides. Complete the editing pass and both quality checkpoints; build and validate the complete entry now."
    log_name = "codex-repair.log" if args.repair else "codex.log"
    command = ["codex", "exec", "--ephemeral", "--skip-git-repo-check", "--sandbox", "workspace-write",
               "-C", str(workspace), "--output-last-message", str(output / manifest.get("result_file", "result.txt")), prompt]
    (output / ("repair-command.json" if args.repair else "command.json")).write_text(json.dumps(command, indent=2) + "\n")
    started = time.monotonic()
    try:
        with (output / log_name).open("w") as log:
            with subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=log,
                                  stderr=subprocess.STDOUT, start_new_session=True, cwd=workspace) as process:
                try:
                    code = process.wait(timeout=args.timeout)
                except subprocess.TimeoutExpired:
                    # Stop the CLI and any tool subprocesses, rather than leaving
                    # an abandoned generation running after the host times out.
                    os.killpg(process.pid, signal.SIGTERM)
                    try:
                        process.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        os.killpg(process.pid, signal.SIGKILL)
                        process.wait()
                    raise
                if code:
                    raise subprocess.CalledProcessError(code, command)
        finish(output, manifest)
    except (subprocess.SubprocessError, RuntimeError, KeyError, ValueError, OSError) as error:
        manifest["status"] = "failed"
        manifest["error"] = str(error)
        raise SystemExit(f"Trial failed: {error}. See {output / log_name}")
    finally:
        log_path = output / log_name
        if log_path.is_file():
            manifest["resolved_config"] = {
                key.replace(" ", "_"): line.removeprefix(key + ": ")
                for line in log_path.read_text(errors="replace").splitlines()[:18]
                for key in ["model", "provider", "reasoning effort"]
                if line.startswith(key + ": ")
            }
        manifest["repair_seconds" if args.repair else "elapsed_seconds"] = round(time.monotonic() - started, 1)
        (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"Validated comparison: {manifest['public']}", flush=True)


if __name__ == "__main__":
    main()
