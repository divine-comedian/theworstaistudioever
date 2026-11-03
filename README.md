# theworstaistudioever

An applied AI studio shipping venture-grade products for underserved, over-instrumented markets. Operationally, it is a daily-cron-driven generator that builds a new startup prototype every day from a Mad-Libs tagline (`{Company} for {subject}`) and publishes it to [theworstaistudioever.com](https://theworstaistudioever.com).

## How it works

1. `cron` fires `scripts/run-daily.sh` once a day.
2. The wrapper reads `pipelines/engine` and runs Codex with `pipeline.md` and the preferred first-attempt skill setup.
3. The agent rolls a non-repeat pair from `seeds/`, generates a concept, builds a landing page + interactive demo screen, regenerates the gallery, and exits.
4. Codex runs a separate QA gate for satire and website behavior, with up to two targeted repair attempts and fresh checks after each.
5. The wrapper generates sharing metadata, validates output, commits, and pushes only after QA passes.
6. GitHub Pages publishes.

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
under `pipelines/codex-v1/`; the original generation prompt remains unchanged.
Codex reuses the server's existing ChatGPT login. The cron time remains
02:00 America/Mexico_City.

The overnight Codex run has a four-hour overall budget: up to 60 minutes for
generation, 30 minutes per QA review, and 45 minutes per repair attempt. There
is one QA gate with at most two repairs. Rejected drafts and QA reports are
preserved privately; failed new entries are removed from the publishable site.
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
