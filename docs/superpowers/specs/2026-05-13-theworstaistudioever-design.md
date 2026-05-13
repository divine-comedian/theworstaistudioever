# theworstaistudioever.com — Design Spec

**Date:** 2026-05-13
**Status:** Approved (pre-implementation)
**Owner:** Mitch Ozmun

## 1. Premise

A daily-cron-driven generator that produces one mock startup prototype per day and publishes it to a public gallery at **theworstaistudioever.com**. Each entry is built around a "Mad Libs" tagline of the form `{Famous Startup} for {subject}` — e.g. *"Tinder for dogs"*, *"Palantir for birds"*, *"Airbnb for fish"*. The site name sets ironic expectations and gives every output a consistent brand voice that absorbs both hits and misses.

## 2. Goals & non-goals

**Goals**
- Produce one new, visually distinct prototype every day, fully autonomously.
- Use Claude Code subscription (`claude -p`) — **zero raw API spend.**
- Each prototype: a landing page + one interactive demo screen.
- Gallery at the root domain is a carousel of all entries, newest first.
- Local-first execution (cron + headless Claude CLI). Migrate to remote `/schedule` routine once quality is consistently good.

**Non-goals (v1)**
- Real functionality / backends in the prototypes (mock data only).
- Multi-page mock products beyond landing + demo.
- Per-prototype repos or subdomains.
- Tracking views / analytics / social posting (later iteration).
- User-facing controls (admin panel, regen button, voting) — later iteration.

## 3. Architecture

Single GitHub repo (`theworstaistudioever`) serves as both code, state, and published site. No backend, no database — the repo *is* the database. GH Pages serves `site/` at the root domain.

```
   ┌──────────────┐   daily 14:00 UTC   ┌──────────────────┐
   │ local cron   │ ───────────────────▶│  claude -p run   │
   └──────────────┘                     └─────────┬────────┘
                                                  │  (single agent, 8 sequential steps)
                              ┌───────────────────┴────────────────────┐
                              ▼                                        ▼
                  read seeds/ + state/history.json           write site/entries/<slug>/
                  pick non-repeat tagline                    rebuild site/index.html
                  generate concept.json                      append state/history.json
                  invoke ui-ux-pro-max + frontend-design     write state/runs/<date>.log
                  + anti-ai-slop                             git commit + push (wrapper)
                                                                       │
                                                                       ▼
                                                      theworstaistudioever.com (GH Pages)
```

Migration to remote (`/schedule` routine) is a delivery change only — same `pipeline.md`, same repo contract.

## 4. Repo layout

```
theworstaistudioever/
├── README.md
├── CLAUDE.md                ← repo-scoped conventions for any agent working here
├── pipeline.md              ← THE prompt — single source of truth for the daily run
├── seeds/
│   ├── companies.json       ← ["Tinder", "Palantir", "Airbnb", ...] ≥100 entries
│   └── subjects.json        ← ["dogs", "birds", "lonely retirees", ...] ≥100 entries
├── state/
│   ├── history.json         ← [{date, company, subject, slug}] — append-only ledger
│   └── runs/
│       └── 2026-05-13.log   ← per-run agent log (always committed)
├── site/                    ← GH Pages root
│   ├── CNAME                ← contains: theworstaistudioever.com
│   ├── index.html           ← carousel gallery, regenerated every run
│   ├── styles.css           ← gallery shell (the meta-site's house style)
│   ├── 404.html
│   └── entries/
│       ├── tinder-for-dogs/
│       │   ├── index.html       ← landing page (self-contained)
│       │   ├── demo.html        ← interactive screen (self-contained)
│       │   ├── concept.json     ← name, tagline, blurb, brand, design_direction, etc.
│       │   └── assets/          ← images only (CSS/JS inlined)
│       └── palantir-for-birds/
│           └── ...
└── scripts/
    ├── run-daily.sh         ← cron entrypoint; wraps `claude -p`
    ├── test-pipeline.sh     ← dry-run against seeds_test.json (5×5)
    └── validate-entry.sh    ← post-build HTML sanity check
```

**Why slug-only URLs:** `theworstaistudioever.com/tinder-for-dogs/` reads like a real product, shares cleanly. Date lives inside `concept.json` for sorting; folder name = slug = URL.

**Why regenerate the gallery from scratch every run:** idempotent, cheap (it's just an HTML re-render from JSON), and a bad render only ever costs one day.

## 5. Seed data

Two flat JSON arrays. Order in the file is irrelevant (random selection). Adding new seeds = a normal PR.

```json
// seeds/companies.json
["Tinder", "Palantir", "Airbnb", "Stripe", "Notion", "Figma", ...]

// seeds/subjects.json
["dogs", "birds", "fish", "lonely retirees", "introverts", "HOAs", ...]
```

**Constraints:**
- Company names: capitalized as the brand presents itself (e.g. "Airbnb" not "AirBnB").
- Subjects: lowercase singular or plural noun phrases — must fit grammatically into `"{Company} for {subject}"`.
- Initial v1 list: ≥100 in each file. Seeds list seeded by hand or by a one-shot generation pass.

**Slug rule:** `slugify(company) + "-for-" + slugify(subject)`, where `slugify(s) = s.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "")`.
Examples:
- `"Palantir"` + `"lonely retirees"` → `palantir-for-lonely-retirees`
- `"Y Combinator"` + `"HOAs"` → `y-combinator-for-hoas`
- `"23andMe"` + `"plants"` → `23andme-for-plants`

## 6. The daily pipeline (8 steps)

Defined in `pipeline.md`, which is the literal text passed to `claude -p`. The agent executes these sequentially and must not skip steps.

### Step 1 — ROLL
- Read `seeds/companies.json`, `seeds/subjects.json`, `state/history.json`.
- Build the PRNG from a seed derived from today's UTC date string (`YYYY-MM-DD`). Every subsequent reroll draws from the same PRNG, so the full reroll sequence for a given day is deterministic — re-running the same day produces the same picks.
- If the picked pair already exists in `history.json`: reroll (next PRNG draw), up to 20 attempts.
- If still no novel pair after 20 attempts: fail loud with `EXHAUSTED`. Wrapper exits non-zero, no commit happens, you add seeds.

### Step 2 — CONCEPT
- Invoke `anti-ai-slop` skill (voice rules for all copy).
- Apply tonal constraint: **dry, self-aware, faux-corporate. Never earnest. The brand is "the worst AI studio ever" — every concept should feel slightly broken but committed to the bit.**
- Generate `concept.json`:
  ```json
  {
    "date": "2026-05-13",
    "tagline": "Palantir for birds",
    "product_name": "...",
    "one_liner": "...",
    "brand_voice_notes": "...",
    "hero": { "h1": "...", "sub": "...", "primary_cta": "..." },
    "features": [ {"title": "...", "blurb": "..."}, ... 3 total ],
    "pricing_tiers": [ {"name": "...", "price": "...", "tagline": "..."}, ... 3 total ],
    "testimonials": [ {"quote": "...", "name": "...", "title": "..."}, ... 3 total ],
    "demo_screen_concept": "describes what the 1 interactive screen shows + does"
  }
  ```

### Step 3 — PLAN (visual direction)
- Invoke `ui-ux-pro-max` skill. Select:
  - **style archetype** from its catalog (e.g. brutalist / claymorphic / bento / editorial / glassmorphism / neumorphism)
  - **palette** from its 161-palette library (or a derived custom one)
  - **font pairing** from its 57 pairings
  - **product-type archetype** for landing page composition
- **Anti-sameness check:** read the last 7 entries' `concept.json` files. The selected (style, palette, fonts) tuple **must not match** any of the last 7. If it would, reselect.
- Write decisions into `concept.json` under `design_direction: { style, palette, fonts, archetype, motion_vocab, hero_composition_notes }`.

### Step 4 — BUILD LANDING
- Invoke `frontend-design` skill — required, not optional. This is the guardrail against generic AI output.
- Build `site/entries/<slug>/index.html`:
  - Self-contained: inline `<style>`, inline minimal JS. No external CSS frameworks (no Tailwind CDN, no Bootstrap).
  - Sections: hero, features (3), fake testimonials (3), pricing (3 tiers), footer, prominent "open demo →" CTA linking to `demo.html`.
  - All copy passed through `anti-ai-slop` voice rules.
  - Implements the (style, palette, fonts, archetype) chosen in step 3.
  - Must visibly differ from prior 7 entries (the design direction check in step 3 enforces this).

### Step 5 — BUILD DEMO
- Build `site/entries/<slug>/demo.html`:
  - One interactive screen of the imagined product, populated with fake data.
  - Real interactivity where cheap: filter, toggle, modal, drag-reorder, tabs. No real API calls — mock everything client-side.
  - Inherits palette + typography from step 3, but uses product-UI layout (not marketing).
  - Back-to-landing link in the chrome.

### Step 6 — GALLERY REBUILD
- Read every `site/entries/*/concept.json`.
- Regenerate `site/index.html` from scratch:
  - Full-bleed carousel, one entry per slide, newest first.
  - Each slide: tagline, brand-colored backdrop derived from that entry's palette, hero h1 preview, "visit →" link to `/entries/<slug>/`.
  - Keyboard nav (←/→), swipe nav on touch, dot indicators.
  - Footer: meta-site identity (`theworstaistudioever`) + total count.
- The gallery uses `site/styles.css` (the stable meta-site shell). It does NOT inline styles like the per-entry pages do — the gallery is the only consistent surface and its CSS lives in a real file so it can be edited without a daily-run touching it. Per-entry pages remain self-contained with inline styles.

### Step 7 — VALIDATE & RECORD
- Run `scripts/validate-entry.sh <slug>`:
  - Both HTML files exist, > 2KB each.
  - Both contain `<html>`, `</html>`, non-empty `<body>`.
  - `concept.json` parses and has all required fields.
- If validation fails: abort before commit, log to run log, exit non-zero.
- If passes: append `{date, company, subject, slug}` to `state/history.json`.
- Write run summary to `state/runs/<date>.log` (what rolled, retries, design choices, any warnings).

### Step 8 — PUBLISH
- The wrapper handles git, not the agent (keeps credentials out of the agent's hands).
- After agent exits 0: wrapper runs `git add . && git commit -m "feat: {tagline}" && git push`.
- GH Pages picks up within ~60 seconds.

## 7. The three-skill design stack

Explicit division of labor — prevents the agent from double-invoking or skipping skills:

| Skill | Role | Invoked in |
|---|---|---|
| `ui-ux-pro-max` | Decides *what* to build — style archetype, palette, fonts, product-type template | Step 3 (once per run) |
| `frontend-design` | Decides *how* to build it — composition, hierarchy, distinctive details that avoid generic AI aesthetics | Steps 4 + 5 |
| `anti-ai-slop` | Polishes all human-facing copy | Inline during steps 2, 4, 5 |

`pipeline.md` makes these invocations mandatory checkpoints — the agent cannot skip them.

## 8. Brand voice (the constraint that makes it work)

Every entry, every gallery string, every meta tag commits to the bit: **"the worst AI studio ever"** — deadpan, faux-corporate, slightly broken. Hero copy reads like a sincere startup pitch that hasn't quite landed. Pricing tiers are absurd but priced with confidence. Testimonials are fake quotes from named "users" with overly specific titles.

Without this voice constraint, the agent defaults to earnest startup-pitch tone, which kills the joke.

The voice rules live in `pipeline.md` and are enforced via the `anti-ai-slop` skill.

## 9. Error handling & failure modes

| Failure | Handling |
|---|---|
| Seed pairs exhausted (20 rerolls) | Agent prints `EXHAUSTED`, exits non-zero. No commit. Notification fires. Manually add seeds. |
| Network flake on `git push` | Wrapper retries push 3× with exponential backoff. |
| Agent produces invalid HTML / empty files | `validate-entry.sh` catches before commit. Run log committed even on failure (separate dry commit on a fail branch — optional). |
| Two cron invocations overlap | `flock` on the repo dir in wrapper; second invocation exits cleanly. |
| `claude -p` hits an unexpected permission prompt | `--allowed-tools` allowlist scopes what's permitted; anything outside hard-fails rather than blocks. |
| Silent rot (run fails for days, you don't notice) | On wrapper exit ≠ 0, fire a notification via ntfy.sh (chosen for v1 — phone push, no account, swappable later). |

## 10. Local cron wrapper

`scripts/run-daily.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

DATE="$(date -u +%F)"
LOG="state/runs/${DATE}.log"
mkdir -p "$(dirname "$LOG")"

# Single-instance lock
exec 9>".run.lock"
flock -n 9 || { echo "Another run in progress — exiting." >&2; exit 0; }

git pull --rebase --autostash >> "$LOG" 2>&1

notify_fail() {
  curl -fsSL -X POST \
    -H "Title: theworstaistudioever cron failed" \
    -d "See state/runs/${DATE}.log" \
    "https://ntfy.sh/${NTFY_TOPIC:?set in env}" || true
}

if ! claude -p "$(cat pipeline.md)" \
      --allowed-tools "Read,Write,Edit,Bash(git diff:*),Bash(git status:*),Bash(node:*),Skill" \
      --max-turns 80 \
      >> "$LOG" 2>&1; then
  echo "RUN FAILED $(date -u)" >> "$LOG"
  notify_fail
  exit 1
fi

# Wrapper does the push — agent never gets push credentials
if ! git diff --quiet || ! git diff --cached --quiet; then
  git add . >> "$LOG" 2>&1
  TAGLINE="$(jq -r '.tagline' "$(ls -td site/entries/*/ | head -1)concept.json")"
  git commit -m "feat: ${TAGLINE}" >> "$LOG" 2>&1
  for i in 1 2 3; do
    if git push >> "$LOG" 2>&1; then break; fi
    sleep $((i * 5))
  done
fi
```

**Crontab:**
```cron
0 14 * * *  /home/mitch/github/theworstaistudioever/scripts/run-daily.sh
```
14:00 UTC = 9am ET. Adjustable.

## 11. Local-first → remote migration path

Once 3–5 consecutive days produce quality you're happy with, migrate to a `/schedule` remote routine. The migration is purely delivery:

1. Add a GitHub PAT (write access to the repo) to the routine's env.
2. Create a `/schedule` routine whose prompt body is the contents of `pipeline.md` plus a wrapper that does `git pull / git push` itself (no shell wrapper available remotely).
3. Disable the local cron entry.
4. Local `run-daily.sh` continues to work as a manual / dev path (`./scripts/run-daily.sh`) for testing prompt changes.

`pipeline.md` does not change. The repo contract does not change.

## 12. Testing

- **`scripts/test-pipeline.sh`**: runs the full pipeline against `seeds/companies_test.json` + `seeds/subjects_test.json` (5×5 each), into a `_test/` subtree, never commits. Used to validate prompt changes before merging.
- **`scripts/validate-entry.sh`**: callable standalone or from the daily run. Checks file existence, sizes, HTML structure, JSON validity.
- **First-week manual review**: every morning for the first week, eyeball the new entry. Adjust `pipeline.md` voice rules / step prompts based on what feels off.

## 13. Out of scope for v1 (explicit)

- Analytics, view tracking, share counts
- Social posting on publish
- Public "vote on today's startup" or user submissions
- AI-generated images / logos (text-and-CSS only for v1; assets/ folder reserved for v2)
- RSS feed (trivial to add later)
- Multi-language

## 14. Open decisions deferred to implementation

- Final crontab time (default 14:00 UTC; user can change).
- Whether `state/runs/<date>.log` is committed on success only or always (default: always, including failures, to make rot visible in `git log`).
- Specific ntfy.sh topic name.
- The initial 100+ seeds — generated as a one-shot pass during implementation; user reviews before first run.
