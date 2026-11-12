#!/usr/bin/env python3
"""Run the selected daily generator; keep Codex tool traces out of public logs."""

import argparse
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

from pipeline_qa import (DraftTransaction, StageFailure, budget, entry_path, execute,
                         RepairAllowance, quality_floor_context, run_qa, validate_config)
from pipeline_editorial import UsageLedger, concept_checkpoint, validate_editorial_config


CLAUDE_TOOLS = "Read,Write,Edit,Glob,Grep,Bash(jq:*),Bash(node:*),Bash(python3:*),Bash(date:*),Bash(ls:*),Bash(cat:*),Bash(mkdir:*),Bash(./scripts/validate-entry.sh:*),Bash(scripts/validate-entry.sh:*),Bash(./scripts/gen-image.sh:*),Bash(scripts/gen-image.sh:*),Skill"


def configuration(workspace):
    bundle = workspace / "pipelines/codex-v1"
    config = json.loads((bundle / "config.json").read_text())
    for name in config["skills"]:
        if not (bundle / "skills" / name / "SKILL.md").is_file():
            raise ValueError(f"Missing frozen daily skill: {name}")
    if type(config["timeout_seconds"]) not in (int, float) or not math.isfinite(config["timeout_seconds"]) or config["timeout_seconds"] <= 0:
        raise ValueError("Codex timeout must be positive")
    validate_config(workspace, config)
    validate_editorial_config(workspace, config)
    return bundle, config


def codex_command(workspace, config, result, read_only=False, schema=None, images=()):
    command = ["codex", "exec", "--ephemeral", "--json", "--skip-git-repo-check",
            "--sandbox", "read-only" if read_only else "workspace-write", "-C", str(workspace),
            "--model", config["model"],
            "-c", 'model_reasoning_effort=' + json.dumps(config["reasoning_effort"]),
            "-c", 'approval_policy="never"',
            "-c", "sandbox_workspace_write.network_access=true",
            "--output-last-message", str(result)]
    if schema:
        command.extend(["--output-schema", str(schema)])
    for image in images:
        command.extend(["--image", str(image)])
    return command + ["-"]


def generate(workspace, bundle, config, run, invoke, recover_today=None, finish_recovery=False, approved=None):
    prompt = (bundle / "adapter.md").read_text() + "\n\n" + (workspace / "pipeline.md").read_text()
    prompt += "\n\nHOST APPROVED QUALITY FLOOR:\n" + json.dumps(quality_floor_context(workspace)[0])
    prompt += """

HOST QA CHECKPOINT OVERRIDE (Codex only; takes precedence over Step 8 abort):
The host runs separate technical and editorial QA after you finish. If metadata
or static validation fails but concept.json parses and both HTML pages exist,
preserve the draft, finish its gallery/history/run-summary checkpoint once, and
report the actual validation errors. Do not start your own repair loop. In this
case print DRAFT_READY: <slug> instead of RUN_COMPLETE. The host will permit up
to two targeted repair attempts and refuse publication unless all checks pass.
If the required draft files cannot be completed, report failure without either
marker. For a validated draft, continue to use RUN_COMPLETE as usual.
"""
    if approved:
        entry = workspace / "site/entries" / approved["slug"]
        entry.mkdir(parents=True)
        (entry / "concept.json").write_text(json.dumps(approved, indent=2, ensure_ascii=False) + "\n")
        prompt += "\n\nHOST APPROVED CONCEPT OVERRIDE:\n" + json.dumps({
            "approved_concept": str(run / "approved-concept.json"),
            "recent_digest": str(run / "recent-entries.json"), "slug": approved["slug"],
        }) + """
The host has completed ROLL and CONCEPT and persisted the approved concept at
the entry's concept.json. Start at Step 3. Do not roll or invent another concept.
Preserve every approved concept field, including its editorial_plan and copy;
extend it with design_direction, brand_kit and image provenance. Use the recent
digest for comparison instead of loading seven complete concept documents.
Generate assets and build the pages around this approved proposition, primary
action and product visual. The host performs final QA and owns all repairs.
"""
    original_history = None
    recovery = None
    if recover_today:
        if Path(recover_today).name != recover_today or recover_today in {".", ".."}:
            raise ValueError("Recovery requires a single entry slug")
        path = workspace / "site/entries" / recover_today / "concept.json"
        concept = json.loads(path.read_text())
        if concept["date"] != datetime.now(timezone.utc).date().isoformat() or concept["slug"] != recover_today:
            raise ValueError("Recovery target must be today's existing entry")
        original_history = (workspace / "state/history.json").read_bytes()
        matches = [item for item in json.loads(original_history) if item.get("slug") == recover_today]
        if len(matches) != 1 or any(matches[0].get(key) != concept[key] for key in ["date", "company", "subject"]):
            raise ValueError("Recovery needs exactly one matching existing history record")
        recovery = {key: concept[key] for key in ["date", "company", "subject", "slug", "product_name", "demo_screen_concept"]}
        (run / "recovery.json").write_text(json.dumps(recovery, indent=2) + "\n")
        prompt += "\n\nTODAY'S UNPUBLISHED ENTRY RECOVERY OVERRIDES:\n" + json.dumps(recovery, indent=2) + """
This is a Codex rebuild of today's unpublished entry, backed up by the host.
These recovery overrides take precedence over the normal ROLL and RECORD steps.
Use the fixed date, company, subject, slug, product name and demo premise above.
Write fresh satire, design, landing page and demo yourself using the daily three
skills. Do not copy the existing HTML. Reuse the existing local image assets
where appropriate and record their real provenance; do not generate new images.
For the anti-sameness check, consider the seven entries before this date and
exclude the entry being rebuilt. Rebuild the gallery normally.
The exact history row is already recorded. Leave state/history.json byte-for-byte
unchanged; do not append a duplicate, remove, or rewrite any history record.
Finish metadata, validation and a run summary for this rebuilt entry, then print
RUN_COMPLETE: """ + recover_today + "\n"
        if finish_recovery:
            prompt += """
RECOVERY CHECKPOINT RESUME: Codex already rebuilt both entry pages in the
previous attempt. It stopped at validation because the validator mistook an
image template inside JavaScript for a literal static image path. The host
fixed that validator and added regression tests.
Preserve the already generated Codex copy, design and image assets. Do not roll
again or rebuild the pages from scratch. Inspect the existing output, finish
the gallery and run summary if needed, run metadata generation and validation,
and emit RUN_COMPLETE only after the checkpoint passes. Leave history unchanged.
"""
    result = invoke(prompt, "generation", config["timeout_seconds"])
    summary = result.read_text()
    markers = [line.split(": ", 1)[1].strip() for line in summary.splitlines()
               if line.startswith(("RUN_COMPLETE: ", "DRAFT_READY: "))]
    if len(markers) != 1:
        raise StageFailure("codex: final response missing a single draft/completion marker; refusing publication")
    slug = markers[0]
    entry = entry_path(workspace, slug)
    if "DRAFT_READY: " in summary:
        if not all((entry / name).is_file() for name in ["concept.json", "index.html", "demo.html"]):
            raise StageFailure("Draft checkpoint is incomplete; refusing publication")
        summary = f"Generation submitted a draft for host QA.\nRUN_COMPLETE: {slug}\n"
    if recover_today and slug != recover_today:
        raise ValueError("Recovery reported the wrong entry; refusing publication")
    if approved:
        concept = json.loads((entry / "concept.json").read_text())
        if slug != approved["slug"] or any(concept.get(key) != value for key, value in approved.items()):
            raise StageFailure("Build changed the approved concept; refusing publication")
    if recovery:
        if (workspace / "state/history.json").read_bytes() != original_history:
            raise ValueError("Recovery changed history; refusing publication")
        path = workspace / "site/entries" / recover_today / "concept.json"
        concept = json.loads(path.read_text())
        if any(concept[key] != recovery[key] for key in ["date", "company", "subject", "slug", "product_name"]):
            raise ValueError("Recovery changed the fixed daily identity; refusing publication")
        concept["generation"] = {"engine": "codex", "model": config["model"],
                                 "reasoning_effort": config["reasoning_effort"],
                                 "generated_at": datetime.now(timezone.utc).isoformat(),
                                 "recovered_unpublished_entry": True}
        path.write_text(json.dumps(concept, indent=2, ensure_ascii=False) + "\n")
    return slug, summary


def run_codex(workspace, recover_today=None, finish_recovery=False, qa_existing=None):
    bundle, config = configuration(workspace)
    # Tool traces, QA evidence, and rejected drafts stay outside public logs/git.
    private = workspace / ".tmp-codex"
    private.mkdir(mode=0o700, exist_ok=True)
    os.chmod(private, 0o700)
    run = Path(tempfile.mkdtemp(prefix=datetime.now(timezone.utc).strftime("%Y-%m-%d-"), dir=private))
    started = time.monotonic()
    deadline = started + config["qa"]["total_timeout_seconds"]
    usage = UsageLedger(run, config)
    allowance = RepairAllowance(config["qa"]["max_repair_attempts"], run)

    def invoke(prompt, label, timeout, read_only=False, schema=None, images=()):
        usage.admit()
        result = run / ("result.txt" if label == "generation" else f"{label}.json" if schema else f"{label}.txt")
        trace = run / ("trace.log" if label == "generation" else f"{label}.log")
        command = codex_command(workspace, config, result, read_only, schema, images)
        try:
            code = execute(command, workspace, trace, budget(deadline, timeout), prompt)
        except StageFailure:
            # Preserve partial usage when possible without hiding a timeout.
            if trace.exists():
                try:
                    usage.record(label, trace)
                except StageFailure:
                    pass
            raise
        usage.record(label, trace)
        if code:
            raise StageFailure(f"codex {label}: exited {code}; private trace: {trace}")
        if not result.is_file() or not result.read_text().strip():
            raise StageFailure(f"codex {label}: missing final response; private trace: {trace}")
        return result

    transaction = DraftTransaction(workspace, run, recover_today or qa_existing)
    passed = False
    try:
        print(f"codex: model={config['model']} reasoning={config['reasoning_effort']} generation_timeout={config['timeout_seconds']}s overall_timeout={config['qa']['total_timeout_seconds']}s", flush=True)
        if qa_existing:
            slug, summary = qa_existing, f"RUN_COMPLETE: {qa_existing}\n"
        else:
            approved = None
            if config.get("concept_checkpoint", {}).get("enabled") and not recover_today:
                approved = concept_checkpoint(workspace, bundle, config, run, invoke, deadline, allowance)
            slug, summary = generate(workspace, bundle, config, run, invoke, recover_today, finish_recovery, approved)
            if not recover_today:
                after = {path.name for path in (workspace / "site/entries").iterdir()}
                if after - transaction.before != {slug} or not transaction.before <= after:
                    raise StageFailure("Generator must create exactly one new entry and preserve existing entries")
        run_qa(workspace, slug, config, run, invoke, deadline, allowance)
        print(summary, end="" if summary.endswith("\n") else "\n")
        print(f"codex: completed with QA in {time.monotonic() - started:.1f}s; private reports: {run}", flush=True)
        print(f"codex: measured input+output tokens={usage.total}; cached/reasoning breakdown in private usage.json", flush=True)
        passed = True
        return 0
    finally:
        if not passed:
            transaction.rollback()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engine", choices=["codex", "claude"], required=True)
    parser.add_argument("--workspace", type=Path, default=Path.cwd())
    parser.add_argument("--preflight", action="store_true")
    parser.add_argument("--recover-today", help="Rebuild today's existing unpublished slug without duplicating history")
    parser.add_argument("--finish-recovery", action="store_true", help="Finish a recovery after a host-fixed validation failure")
    parser.add_argument("--qa-existing", help="Run the QA gate on an existing draft, without generating or appending history")
    args = parser.parse_args()
    if args.finish_recovery and not args.recover_today:
        parser.error("--finish-recovery requires --recover-today")
    if args.qa_existing and args.recover_today:
        parser.error("--qa-existing cannot be combined with --recover-today")
    workspace = args.workspace.resolve()
    if not shutil.which(args.engine):
        raise SystemExit(f"Missing generator on PATH: {args.engine}")
    try:
        if args.engine == "codex":
            _, config = configuration(workspace)
            browser = subprocess.run(["node", "scripts/check-entry-browser.cjs", "--preflight"], cwd=workspace,
                                     capture_output=True, text=True, timeout=30)
            if browser.returncode:
                raise ValueError("Daily QA requires installed Playwright and Chromium; browser preflight failed")
            if args.preflight:
                print(f"codex preflight: {config['model']}, {config['reasoning_effort']}, three frozen v1 skills")
                print(f"QA preflight: concept checkpoint={config.get('concept_checkpoint', {}).get('enabled', False)}, up to {config['qa']['max_repair_attempts']} shared repairs, {config['qa']['total_timeout_seconds']}s overall budget")
                return
            raise SystemExit(run_codex(workspace, args.recover_today, args.finish_recovery, args.qa_existing))
        if args.recover_today or args.qa_existing:
            raise ValueError("Entry recovery and QA are supported by the Codex engine")
        prompt = workspace / "pipelines/claude-backup/pipeline.md"
        if not prompt.is_file():
            raise ValueError("Missing archived Claude prompt")
        if args.preflight:
            print("claude preflight: archived prompt available")
            return
        raise SystemExit(subprocess.run(["claude", "-p", prompt.read_text(),
                                        "--allowed-tools", CLAUDE_TOOLS, "--max-turns", "80"],
                                       cwd=workspace).returncode)
    except StageFailure as error:
        print(f"generator failed: {error}", file=sys.stderr)
        raise SystemExit(error.code)
    except (OSError, ValueError, KeyError, subprocess.TimeoutExpired) as error:
        raise SystemExit(f"generator failed: {error}")


if __name__ == "__main__":
    main()
