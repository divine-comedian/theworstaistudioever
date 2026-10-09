# theworstaistudioever

An applied AI studio shipping venture-grade products for underserved, over-instrumented markets. Operationally, it is a daily-cron-driven generator that builds a new startup prototype every day from a Mad-Libs tagline (`{Company} for {subject}`) and publishes it to [theworstaistudioever.com](https://theworstaistudioever.com).

## How it works

1. `cron` fires `scripts/run-daily.sh` once a day.
2. The wrapper invokes `claude -p < pipeline.md`.
3. The agent rolls a non-repeat pair from `seeds/`, generates a concept, builds a landing page + interactive demo screen, regenerates the gallery, and exits.
4. The wrapper generates sharing metadata, validates output, commits, and pushes.
5. GitHub Pages publishes.

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

Success/failure is reported to Telegram, reusing the aurevon-outreach bot
(`TELEGRAM_BOT_TOKEN` + `TELEGRAM_USER_ID` read at runtime from
`~/github/aurevon-outreach/.env`). On success the message includes the new
startup name and a link to its live page. No `.env` is required here unless you
want to override the bot/chat — see `.env.example`.

## Dry run (no commit, uses 5×5 test seeds)

```bash
./scripts/test-pipeline.sh
```

## Add seeds

Edit `seeds/companies.json` (capitalized brand names) or `seeds/subjects.json` (lowercase noun phrases). PR + merge. Next day's run picks them up automatically.

## Inspect a run

```bash
cat state/runs/2026-05-13.log
```

## Disable local cron (for migration to remote `/schedule` routine)

```bash
crontab -l | grep -v theworstaistudioever | crontab -
```

The spec for this system lives at `docs/superpowers/specs/2026-05-13-theworstaistudioever-design.md`.
