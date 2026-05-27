# theworstaistudioever

A daily-cron-driven generator that builds a new mock startup prototype every day from a Mad-Libs tagline (`{Company} for {subject}`) and publishes it to [theworstaistudioever.com](https://theworstaistudioever.com).

## How it works

1. `cron` fires `scripts/run-daily.sh` once a day.
2. The wrapper invokes `claude -p < pipeline.md`.
3. The agent rolls a non-repeat pair from `seeds/`, generates a concept, builds a landing page + interactive demo screen, regenerates the gallery, and exits.
4. The wrapper validates output, commits, and pushes.
5. GitHub Pages publishes.

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
