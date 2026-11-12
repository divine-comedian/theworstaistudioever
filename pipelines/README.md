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

Normal Codex runs have two host-controlled checkpoints. The host rolls a fixed
pair and supplies a compact recent-entry digest. A read-only Codex invocation
drafts structured concept JSON; a second independently reviews it before the
host persists `approved-concept.json` and permits asset generation and building.
The brief records three audience observations with actual comic consequences,
source-product patterns, an opening composition plan and `audience_design`.
That plan requires at least two concrete audience-associated visual references
and their application to the landing and demo. The source company supplies the
service structure and workflow; the audience supplies type, color, imagery and
visual composition. Repeated audiences can share cultural cues without cloning
an earlier identity. Novelty must not override audience fit. The build must
preserve its approved fields.

Final QA independently checks comprehension, satire, composition and continuity,
desktop/mobile screenshots and an executable demo interaction. Reviewers see a
host-extracted copy/JavaScript packet before explanatory concept documents.
The host attaches nine current-page screenshots and three frozen approved-reference
images directly to the CLI invocation and
inlines compact review inputs, avoiding reliance on a reviewer choosing to open
image files or repeatedly reading packet files. A structured visual audit must
cover both pages at desktop/mobile and agree with the composition verdict.
Every feature and pricing perk needs a concise, explicit behavior/mechanic audit.
The user-approved repaired Again entry (2026-11-11) is a permanent minimum
quality reference in `quality-floor.json`. Its three screenshots are frozen
under `reference/again-approved/` and verified against recorded SHA-256 hashes
before model calls. They do not rotate with the recent-entry digest. Drafting,
building and repairs receive its rubric; final review receives the attached
reference images and must provide a comparison for all four acceptance checks.
A below-standard assessment prevents a pass and requires repair or withholding
publication. Different palettes, layouts and identities are expected; the
comparison concerns clarity, specific humor, purposeful visuals and finish.
Reviewers read as casual outsiders and identify the setup and comic turn in
each feature's actual copy. Explaining a plausible niche service is insufficient.
Final visual audits name visible `audience_cues` and an `audience_fit_pass` for
each page and viewport; a mismatch cannot accompany a composition pass.
Browser checks cover 1440px desktop, 390px mobile and 320px narrow mobile.
Screenshot labels include their widths. Interaction checks explicitly load
deferred images before judging missing assets, including images inside closed
panels; valid lazy loading is not a product failure.
Missing audit coverage or a failed acceptance check cannot accompany a pass.
Hierarchy and image usefulness can fail even when there is no clipping.
Deterministic metadata, asset, HTML and browser checks must also pass.
Known human copy findings live in `codex-v1/editorial-regressions.json`, keyed
by entry slug. The host checks their rejected phrases in concept, landing and
demo on every QA attempt. These findings cannot disappear because a later model
review omitted them. The reviewer also checks that replacements resolve the
underlying meaning; phrase removal alone does not establish editorial quality.

If QA finds defects, the host consumes one shared repair allowance. Concept
repairs return revised JSON without editing the site. Final findings include
stable IDs, exact targets, requested changes and acceptance conditions. A batch
of unique literal replacements can be applied directly when technical checks
pass; stale, ambiguous or instruction-based changes use a bounded repairer.
Every repair is followed by fresh checks and independent review. Verifiers must
explicitly resolve or retain each earlier finding ID. There are **at most two
repair batches total across both checkpoints**, including host-applied patches.
A passing initial review needs no repair. Failure
after the second attempt stops publication. A CLI failure, invalid QA report,
or timeout also stops publication rather than being interpreted as a pass.
Codex may submit complete draft files with `DRAFT_READY` when its static check
fails; this permits the host's bounded repair stage to fix the draft. The host
emits public `RUN_COMPLETE` only after the QA gate passes.

The three frozen skills remain unchanged. Concept review uses
`codex-v1/concept-qa.md`; final QA uses `codex-v1/qa.md`; page repairs use
`codex-v1/heal.md`. Repairs
preserve product identity, visual direction and images, and cannot alter history,
other entries, scripts or the pipeline configuration. Sharing metadata is rebuilt
after each repair. Installed Playwright and matching Chromium are required;
preflight checks them without installing anything.

Time limits in `codex-v1/config.json` are 5 minutes for concept drafting, 3 for
concept review, 5 for concept repair, 60 for building, 8 for final review,
10 per page repair and 5 per final verification, with **two hours overall**.
Every subprocess uses the smaller of its stage allowance and the remaining
overall budget. These are ceilings; successful stages finish immediately.

All Codex invocations use `--json`, `--ephemeral`, schema-constrained reviews and
explicit non-interactive approvals. Completed-turn usage events are recorded in
private `usage.json`, including input, cached input, output and available
reasoning-output counts. The accounting total is input + output; cached input
and reasoning output are breakdowns, not additional charges. Missing required
usage events stop publication. Failed/timed-out calls retain available evidence;
in-flight usage without a completed event cannot be inferred from the CLI.

`usage.max_total_tokens` optionally limits a run's measured token allowance;
`usage.max_stage_tokens` accepts exact stage names or families such as `concept`,
`generation`, `review` and `repair`. Limits are positive integers or null. They
are checked after completed calls and before another invocation, so the current
turn may exceed them. These are token admission controls, not dollar or hard
in-flight caps. The provisional `review` allowance is 75,000 tokens: the attached
image calibration used 34,179 and final QA on the repaired entry used 42,587.
Other numeric allowances remain unset pending measurement; timeouts and repair
limits bound execution now. No experimental
budget feature or additional API billing is required.

Explicit user-requested artwork corrections may declare a version 2 mixed kit
with a nonempty `revision_reason`. This accepts documented
`openai-imagegen`/`image_gen` replacement graphics with their actual prompts.
A user-requested logo replacement additionally requires a nonempty
`logo_revision_reason` and the same honest image_gen provenance; an artwork
revision alone retains the original logo requirement.
This does not change the daily generator's Gemini workflow,
waive the two composed-graphics requirement, or relabel replacement art as Gemini.

Private `.tmp-codex/<run>/` artifacts include the original draft, each review,
repair traces, technical reports, screenshots and `qa-summary.json`. On a failed
new generation, the rejected entry is moved out of `site/entries/` into those
private artifacts and the previous gallery/history are restored. This prevents
a later daily commit from accidentally publishing a rejected draft. Existing
drafts are backed up and restored on failure.
Concept-only failures leave no new entry under `site/entries/`. Explicit recovery
and `--qa-existing` operate on their existing fixed draft and skip concept drafting;
final QA, usage accounting and the repair allowance still apply.

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
