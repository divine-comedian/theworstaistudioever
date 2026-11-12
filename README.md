# theworstaistudioever

An applied AI studio shipping venture-grade products for underserved, over-instrumented markets. Operationally, it is a daily-cron-driven generator that builds a new startup prototype every day from a Mad-Libs tagline (`{Company} for {subject}`) and publishes it to [theworstaistudioever.com](https://theworstaistudioever.com).

## How it works

1. `cron` fires `scripts/run-daily.sh` once a day.
2. The wrapper reads `pipelines/engine` and runs Codex with `pipeline.md` and the preferred first-attempt skill setup.
3. The host rolls a non-repeat pair from `seeds/`. Codex drafts a concept; a separate read-only invocation reviews it before assets or HTML are generated.
4. Codex builds the approved concept, then final QA checks comprehension, satire, composition, consistency and actual demo behavior. Both checkpoints share at most two repair batches, with fresh verification after each.
5. The wrapper generates sharing metadata, validates output, commits, and pushes only after QA passes.
6. GitHub Pages publishes.

The repaired Again entry approved on November 11, 2026 is the minimum quality
standard for every daily run. Its rubric and three frozen screenshots live in
`pipelines/codex-v1/quality-floor.json` and its referenced files. Concept drafting,
building and QA receive that standard. Final QA must explicitly establish that
the entry meets it in clarity, satire, composition and continuity before
publication. Entries retain their own identities and ideas.

The source company supplies each demo's service structure and workflow; its
audience supplies the visual identity. Concept approval requires concrete
audience references and their application to both pages before artwork is made.
Satire must have an understandable setup and comic turn for a casual outsider;
plausible niche services alone do not pass. Final visual QA explicitly checks
audience fit on both pages at desktop and mobile sizes.

The daily Codex pipeline also receives a [text-only Impeccable adaptation](pipelines/codex-v1/design-guidance/impeccable/GUIDE.md)
for visual critique, responsive layout, accessibility and interaction recovery.
The source revision, license, adaptation notes and hashes are recorded locally.
Only relevant documents are inlined for each stage. Preflight rejects changed
guidance, extra files, symlinks and executable files. No upstream engine, installer,
hook, live mode, catalog or account integration is included. The existing three
skills, satire rules, audience references and independent QA remain authoritative.

Each new entry's landing page and demo include static Open Graph and Twitter
metadata. Preview titles use `product_name — tagline`; descriptions combine the
hero heading and paragraph, capped at 300 characters with an ellipsis. Hero
images use absolute URLs to a 1200×630 JPEG derived from the hero, with the studio
logo as the fallback on image-less entries. The generator reads the domain from
`site/CNAME`.

To refresh an existing entry after changing its concept or hero copy:

```bash
python3 scripts/build-entry-metadata.py site paypal-for-flat-earthers
./scripts/validate-entry.sh site paypal-for-flat-earthers
```

## Daily run — manual

```bash
./scripts/run-daily.sh
```

The scheduled job now uses **Codex, gpt-6.1-sol at high reasoning**, with the
same three skills used by the preferred first comparison. That setup is frozen
under `pipelines/codex-v1/`; `pipeline.md` includes the current brand-kit workflow.
Codex reuses the server's existing ChatGPT login. The cron time remains
02:00 America/Mexico_City.

Each new entry gets a brand kit with a **Gemini-designed logo**, monochrome and
favicon exports, a graphic language, design tokens, and at least two composed
graphic-design assets. Gemini designs the artwork; Codex briefs it and integrates
it into the landing page and demo. Campaign posters, editorial illustration and
infographics qualify; additional photographs and basic HTML/SVG diagrams do not.
Intentional typography is allowed in designed artwork, with spelling/number and
mobile-legibility checks and a live-text equivalent for essential information.
The image helper accepts `--reference <local-image>` so the approved logo can
guide related graphics and variants.

Gemini can generate up to **12 distinct assets per entry**, with one corrective
regeneration per asset. The shared default budget is **24 successful API calls
per UTC day**, raised from 10; calls returning HTTP 200 count even if the image
is later rejected. Set `GEMINI_IMAGE_DAILY_LIMIT` in the environment or `.env`
to change that budget. API failures use bounded retries without charging the
counter. Missing API access or an exhausted budget falls back to native
SVG/HTML/CSS branding with an explicitly declared fallback reason. Version 2
kits validate Gemini design provenance and actual graphic image placements, as
well as logo/favicon use on both pages. Historical version 1 kits remain compatible.

The overnight Codex run has a two-hour overall ceiling: up to 5 minutes to draft
a concept, 3 to review it, 60 to build, 8 for final QA, 10 per page repair and 5
per final verification. Concept repair has a 5-minute ceiling. Both checkpoints
share two repair attempts. Uniquely matched literal text patches can skip the
repair model call, but still require verification. Per-stage input, cached input,
output and available reasoning-token counts stay in private `usage.json` reports.
Optional token allowances block further stages after completed-turn accounting;
they are not hard in-flight spending caps. Visual QA attaches screenshots
directly, supplies compact inline inputs and requires desktop/mobile visual
observations. Review calls have a provisional 75,000-token allowance after a
34,179-token negative-sample review and a 42,587-token repaired-entry review.
Other token allowances remain unset pending measurement; deadlines and repair
limits are active. Rejected
drafts and QA reports are preserved privately; failed new entries are removed from the publishable site.
See [QA and repair details](pipelines/README.md#qa-and-repair-before-publication).

The original Claude prompt, wrapper, dry-run harness, settings, and documentation
are preserved under `pipelines/claude-backup/`, with checksums. To switch the
scheduled job back to Claude:

```bash
printf 'claude\n' > pipelines/engine
./scripts/run-daily.sh --preflight
```

Use `printf 'codex\n' > pipelines/engine` to return to Codex. See
[pipeline and rollback details](pipelines/README.md). A `PIPELINE_ENGINE`
environment or `.env` setting overrides the selector.

Success/failure is reported to Telegram, reusing the aurevon-outreach bot
(`TELEGRAM_BOT_TOKEN` + `TELEGRAM_USER_ID` read at runtime from
`~/github/aurevon-outreach/.env`). On success the message includes the new
startup name and a link to its live page. No `.env` is required here unless you
want to override the bot/chat — see `.env.example`.

## Dry run (no commit, uses 5×5 test seeds)

```bash
./scripts/test-pipeline.sh
```

This uses the selected engine in `_test/daily/`, preserving earlier comparison
previews. It never commits, pushes, or sends notifications. Image generation is
skipped when no key is supplied to the dry-run environment. Codex raw traces
stay in the ignored `.tmp-codex/` directory inside its workspace; only its final
summary enters the normal run log.

For a headless preview, serve `_test/daily/site` on the server and forward the
port from your workstation:

```bash
# Server, from the repository root:
python3 -m http.server 4173 --bind 127.0.0.1 --directory _test/daily/site
# Workstation:
ssh -L 4173:127.0.0.1:4173 <server>
```

Then open `http://127.0.0.1:4173/` in your workstation's browser.

## Add seeds

Edit `seeds/companies.json` (capitalized brand names) or `seeds/subjects.json` (lowercase noun phrases). PR + merge. Next day's run picks them up automatically.

## Compare Codex with an existing Claude entry

The comparison script below retains the experimental revision-2 setup. The
scheduled job uses the preferred first attempt's frozen setup instead.

```bash
python3 scripts/compare-codex.py --entry notion-for-wedding-djs
```

Requires an installed, signed-in Codex CLI and the three existing writing/design
skills (`anti-ai-slop`, `frontend-design`, `ui-ux-pro-max`). It also loads the
repository's copy of OpenAI's `frontend-skill`; its source is recorded in
`prompts/skills/frontend-skill/SOURCE.json`. The trial uses the
CLI's configured model and reasoning setting; the resolved settings appear in
`codex.log`. Codex supports this scripted workflow through
[`codex exec`](https://learn.chatgpt.com/docs/non-interactive-mode).

The script creates a separate workspace in `/tmp` and records the run under
`_test/codex-comparison/`. It gives Codex the same product name, demo premise,
photographs, and preceding seven concepts, but withholds the original entry's
HTML, marketing copy, and design direction. Codex writes its own landing page,
demo, copy, and design. Image generation is skipped so both versions use the
same assets. No production history, entries, cron settings, notifications, or
publishing steps are changed.

The host reruns metadata generation and validation before creating a `public/`
comparison directory with links to both versions. Only serve that directory;
the surrounding trial directory contains logs and local workspace paths. This
is a single labelled trial, so review the satire, mobile layout, and demo
interactions before deciding whether to migrate the daily job.

Use `--prepare-only` to inspect inputs first, then `--prepared <trial-directory>`
to run them. The default generation timeout is 20 minutes; `--timeout <seconds>`
changes it. Failed runs keep their logs and workspace for inspection and do not
create a public comparison. Run the isolation check with:

```bash
python3 scripts/test-compare-codex.py
```

The revised Codex quality contract lives in `prompts/codex-quality.md`. It
requires a source-product UX plan, distinct decisions for marketing and product
surfaces, and a copy-editing pass grounded in specific audience behavior. The
runner checks for the resulting `quality-plan.json` and `quality-review.json`
before accepting output; these artifacts document decisions and do not replace
browser checks or the user's judgment. Concept-specific comparison requirements
live in `prompts/comparisons/<slug>.json`. Cuebook's requirements preserve the
original product brief and add the user's feedback about Notion fidelity,
clean SaaS composition, and stronger satire. The baseline's copy and HTML remain
withheld, and previous comparisons are preserved in their own trial directories.

After browser checks identify a concrete defect, one bounded Codex repair pass
can consume a text report without regenerating the concept or rewriting its
copy and design:

```bash
python3 scripts/compare-codex.py --repair <trial-directory> --feedback <report.txt>
```

The runner retains the initial generation log and result, records the repair
separately, rechecks the quality artifacts and validates the entry. A second
repair invocation for that trial is rejected. Browser checks must then be rerun
against the repaired output.

## Inspect a run

```bash
cat state/runs/2026-05-13.log
```

## Disable local cron (for migration to remote `/schedule` routine)

```bash
crontab -l | grep -v theworstaistudioever | crontab -
```

The spec for this system lives at `docs/superpowers/specs/2026-05-13-theworstaistudioever-design.md`.
