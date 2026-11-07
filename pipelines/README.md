# Daily generator and rollback

`engine` selects the scheduled generator. It is currently `codex`. The existing
02:00 America/Mexico_City cron entry still calls `scripts/run-daily.sh`; that
wrapper reads this selector each run. `PIPELINE_ENGINE` in the environment or
repo `.env` overrides the selector.

## Active Codex setup

`codex-v1/config.json` pins the preferred first comparison's model and reasoning:
`gpt-6.1-sol`, `high`. Its three skill directories were copied from the exact
first-trial workspace, including their datasets and helper scripts. Their
provenance and hashes are recorded in `codex-v1/manifest.json`.

The generator executes the current root `pipeline.md` with the thin
`codex-v1/adapter.md`. The revision-2 experimental quality contract, fourth
frontend skill, and Cuebook-specific requirements are outside this daily setup.
The current prompt requires a Gemini-designed logo family, brand kit, design
tokens and at least two composed graphic-design assets. The coding agent briefs
and integrates; photographs and primitive code diagrams do not fulfil the graphic
requirement. Approved artwork is passed to Gemini with `--reference` for matching
graphics/variants. Version 2 validation checks provenance and visible graphic
placements, accepts raster logo exports, and keeps older kits compatible.
Gemini supports up to 12 distinct assets per
entry (two attempts each), with a shared default cap of 24 successful calls per
UTC day. `GEMINI_IMAGE_DAILY_LIMIT` overrides the cap; the image script serializes
budget checks and charges. Missing Gemini access falls back to native SVG/HTML/CSS.
Declared kits are checked by `scripts/validate-brand-kit.py` through the normal
entry validator. Codex gets a
60-minute generation limit, workspace write access, and network access for existing image
and rendering tools. Git and notifications remain wrapper responsibilities.

Raw Codex traces stay under `.tmp-codex/`, ignored by git and restricted to the
current user. The final response and run status go to `state/runs/` as before.

## QA and repair before publication

Every Codex run goes through one host-controlled QA gate. The initial review is
read-only, in a fresh non-interactive Codex process. It checks satire coherence,
references, continuity across concept/landing/demo, desktop and mobile screenshots,
and an actual demo interaction. Deterministic metadata, asset, HTML and browser
checks also have to pass; a model verdict cannot waive a technical failure.
Known human copy findings live in `codex-v1/editorial-regressions.json`, keyed
by entry slug. The host checks their rejected phrases in concept, landing and
demo on every QA attempt. These findings cannot disappear because a later model
review omitted them. The reviewer also checks that replacements resolve the
underlying meaning; phrase removal alone does not establish editorial quality.

If QA finds defects, Codex makes a targeted repair, followed by all checks and a
fresh review. There are **at most two repair attempts total**, not two per issue
or an open-ended outer loop. A passing initial review needs no repair. Failure
after the second attempt stops publication. A CLI failure, invalid QA report,
or timeout also stops publication rather than being interpreted as a pass.
Codex may submit complete draft files with `DRAFT_READY` when its static check
fails; this permits the host's bounded repair stage to fix the draft. The host
emits public `RUN_COMPLETE` only after the QA gate passes.

The three frozen skills remain unchanged. QA
instructions are in `codex-v1/qa.md`; repairs use `codex-v1/heal.md`. Repairs
preserve product identity, visual direction and images, and cannot alter history,
other entries, scripts or the pipeline configuration. Sharing metadata is rebuilt
after each repair. Installed Playwright and matching Chromium are required;
preflight checks them without installing anything.

Time limits in `codex-v1/config.json` are 60 minutes for generation, 30 minutes
per review, 45 minutes per repair, and **four hours overall**, including checks.
Every subprocess uses the smaller of its stage allowance and the remaining
overall budget. These are ceilings; successful stages finish immediately.

Private `.tmp-codex/<run>/` artifacts include the original draft, each review,
repair traces, technical reports, screenshots and `qa-summary.json`. On a failed
new generation, the rejected entry is moved out of `site/entries/` into those
private artifacts and the previous gallery/history are restored. This prevents
a later daily commit from accidentally publishing a rejected draft. Existing
drafts are backed up and restored on failure.

To run QA and optional targeted repairs on an existing draft without publishing:

```bash
python3 scripts/run-pipeline-agent.py --engine codex --qa-existing <slug>
```

`--publish-existing` also runs this gate when Codex is selected. Claude rollback
continues to use its archived original prompt and shared static validation.

## Restore Claude

From the repository root, change the selector and verify dependencies:

```bash
printf 'claude\n' > pipelines/engine
./scripts/run-daily.sh --preflight
```

The next scheduled run will invoke Claude with the archived original prompt,
tool allowlist, and 80-turn cap. This keeps the repaired shared SEO/publishing
wrapper. For one run without changing the selector:

```bash
PIPELINE_ENGINE=claude ./scripts/run-daily.sh
```

To return to Codex:

```bash
printf 'codex\n' > pipelines/engine
./scripts/run-daily.sh --preflight
```

`claude-backup/` preserves the original prompt, wrapper, dry-run script, cron
PATH regression test, Claude permissions and conventions, environment template,
and README. `claude-backup/manifest.json` records their checksums and the original
Git revision. Credentials are excluded. These are archival copies; execute the
live wrapper with the selector rather than executing scripts inside the backup
directory. Claude's existing CLI login and installed plugins are retained.

The Claude backup retains the original generation prompt, before the brand-kit
upgrade. `codex-v1/manifest.json` records the original first-trial prompt hash
and skill provenance, not a checksum of the evolving root prompt. Keep the
backup unchanged when updating daily instructions. The shared image script's
new daily budget also applies to Claude rollback; its archived prompt still
uses the original four-image allocation.

## Recover an unpublished entry

Back up the entry, gallery, history and run log before recovery. The generator
can rebuild today's existing slug with its fixed identity and existing images,
leaving history byte-for-byte unchanged:

```bash
python3 scripts/run-pipeline-agent.py --engine codex --recover-today <slug>
```

After reviewing and validating the result, publish through the existing wrapper
without generating a second entry:

```bash
./scripts/run-daily.sh --publish-existing <slug> --no-notify
```

The wrapper revalidates sharing metadata and the entry, rebuilds SEO fixtures,
then performs its normal commit and push. `--no-notify` suppresses Telegram for
that invocation. A normal scheduled run retains the existing notifications.
