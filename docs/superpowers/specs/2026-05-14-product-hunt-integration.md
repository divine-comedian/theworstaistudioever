# Product Hunt integration — Future Feature Spec

**Date:** 2026-05-14
**Status:** Idea — not scheduled
**Owner:** Mitch Ozmun

## 1. Premise

Plug Product Hunt's public product stream into the daily pipeline so that some entries riff on **real, currently-trending products** instead of (or in addition to) the static seed company list. Today the tagline is `{seeds/companies.json random} for {seeds/subjects.json random}`. After this feature, some fraction of days could roll instead as `{today's PH product} for {seeds/subjects.json random}` — making the studio's output feel topical and self-aware, not just permutational.

## 2. Goals & non-goals

**Goals**
- Inject a periodic dose of zeitgeist into the daily generator without changing the brand voice.
- Stay within the spec's "zero raw API spend" rule — Product Hunt's API is free; this constraint is unaffected.
- Keep the local-first execution model: any network call is part of the wrapper or the pipeline itself, not an external service.
- Make the new source feel **optional and weighted**, not mandatory. E.g. 1-in-N days draws from PH; the rest still draw from `seeds/companies.json`.

**Non-goals**
- Becoming a PH analytics tool. We don't care about votes, comments, or trend lines beyond "pick something."
- Multi-day continuity (e.g. "yesterday's PH winner gets a sequel").
- Mocking the actual PH product's space — the gag is still "{name} for {weird subject}", we just use a fresher name.

## 3. Two data sources, two paths

Product Hunt exposes two viable read paths (verified 2026-05-14):

### 3a. RSS / Atom feed — **no auth**
- URL: `https://www.producthunt.com/feed`
- Format: Atom 1.0
- Per-entry fields available: `id`, `title` (product name), `published`, `updated`, `link[@rel="alternate"]` (product URL), `content` (HTML containing the one-line tagline), `author/name` (submitter).
- Not available: vote count, image, topic tags, rank.
- Ordering: roughly recency, **not** by votes.

**Use this when:** the gag only requires a current product name. Wrapper does a single unauthenticated `curl` + parse, no token management, no rate-limit worry.

### 3b. GraphQL API v2 — **requires Bearer token**
- Endpoint: `https://api.producthunt.com/v2/api/graphql`
- Auth: create an app at `producthunt.com/v2/oauth/applications`, copy the **developer token** (no OAuth dance required for read-only).
- Token lives in `.env` as `PRODUCT_HUNT_TOKEN`.
- Example query: `posts(order: VOTES, first: 10) { edges { node { name tagline votesCount url thumbnail { url } } } }`.
- Free tier rate limit is generous for one-call-per-day.

**Use this when:** we want today's **top** product specifically, or we want the thumbnail/tagline to seed the design direction.

**Recommendation:** start with 3a (RSS). It's enough for the gag and adds zero new failure surface (no token rotation, no rate-limit recovery). Migrate to 3b only if a future iteration needs vote-ranking or images.

## 4. Pipeline changes

`pipeline.md` Step 1 currently:

> Roll a `{company, subject}` pair from `seeds/companies.json` and `seeds/subjects.json` that does not appear in `state/history.json`.

Proposed Step 1 update (RSS variant):

> With probability **P** (default 0.25, configurable via `PRODUCT_HUNT_WEIGHT` env var):
>   - Fetch `https://www.producthunt.com/feed`. Parse the Atom feed. Take the most recent 20 entries. Filter out any product name already in `state/history.json` (matched on `company` field).
>   - If the filtered list is empty, fall back to the seed roll.
>   - Otherwise, draw one entry at random. Use its `<title>` as the `company` value. Use its `<content>` tagline as a **brand_voice_notes** hint for the design step.
>
> Otherwise, fall back to the existing seed-list roll.

Everything downstream (slug generation, design direction, validation, gallery regen) is unchanged. `concept.json` gets one new optional field:

```json
{
  "company_source": "product_hunt",
  "product_hunt_url": "https://www.producthunt.com/products/<slug>"
}
```

This makes it auditable later — `jq` queries against history can answer "what fraction of entries came from PH?"

## 5. Wrapper changes (`scripts/run-daily.sh`)

None required for path 3a. The pipeline itself does the fetch via the `Bash(curl:*)` allowlist (which would need to be added to the `--allowed-tools` flag).

For path 3b, the wrapper would need to source `PRODUCT_HUNT_TOKEN` from `.env` (already loaded) and pass it through. Either path adds **one line** to the allowlist.

## 6. Seed-data implications

- `seeds/companies.json` stays as the primary universe. PH is an **augment**, not a replacement.
- Over time, "today's PH product" names will appear in `state/history.json`'s `company` field. The non-repeat check naturally prevents the same PH product showing up twice — no separate dedupe state needed.
- Subject list (`seeds/subjects.json`) is untouched. The mashup still works.

## 7. Failure modes

| Mode | Behavior |
|---|---|
| PH feed 404 / timeout | Fall back to seed roll; log warning; continue. |
| Atom parser fails on malformed XML | Fall back to seed roll; log warning. |
| All recent PH products already in history | Fall back to seed roll. |
| Network blocked entirely (no DNS) | Fall back to seed roll. The PH branch is never load-bearing. |

The fallback discipline is the whole point: the daily run must produce **something**, every day, regardless of any external dependency's health.

## 8. Why this fits the brand

The studio's voice is "worst AI studio ever — deadpan, faux-corporate, drily commits to bad ideas." Riffing on **real current products** sharpens the bit, because the audience can verify the source product exists and is unrelated. *"Lumox for jury duty"* lands harder than *"Tinder for jury duty"* because Lumox is a real obscure thing someone shipped this week, and the studio is treating it like a known commodity.

## 9. Open questions

- **PH product names are sometimes long or branded weirdly** (`c15t 2.0`, `Lumox`, `PTOFlow`). Slug generation in `pipeline.md` Step 4 may need a normalization pass to keep URLs clean (`/c15t-2-0-for-jury-duty/` is fine; the existing slug logic should already handle this, but worth verifying when implementing).
- **What is P?** 0.25 is a guess. Could be tunable per run; could be deterministic (e.g. "every 4th day").
- **Do we cite the source on the entry page?** Argument for: transparency, honesty. Argument against: breaks the deadpan brand voice — the studio should not acknowledge that it borrows. Lean: no citation in the page, but record `product_hunt_url` in `concept.json` for internal honesty.

## 10. When to build this

After:
- Cron is installed and running daily (Task 10 from the original plan).
- A week or two of pure-seed entries has shipped — establishes a baseline before adding variance.
- The `RUN_COMPLETE` reliability issue is fully resolved (already loosened in the wrapper as of `ee06444`, but worth confirming the next manual run goes clean end-to-end).
