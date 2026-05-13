# theworstaistudioever.com Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up a daily-cron-driven generator at `theworstaistudioever.com` that produces one Mad-Libs-tagline mock startup per day (landing page + interactive demo screen) using `claude -p` (zero API spend), publishing to a GH Pages carousel.

**Architecture:** Single GitHub repo serves as code, state ledger, and published site. A local cron fires `scripts/run-daily.sh`, which invokes `claude -p` with `pipeline.md` as the prompt. The agent rolls a non-repeat `{Company} for {subject}` pair from seed JSON, generates a concept, invokes the three-skill design stack (`ui-ux-pro-max` → `frontend-design` → `anti-ai-slop`), writes a self-contained entry folder, regenerates the carousel index, and exits. The wrapper handles git and notifications.

**Tech Stack:** Bash 5+ (wrapper, validators), `jq` (JSON ops in shell), `flock` (single-instance lock), `curl` (ntfy.sh notifications), Claude Code CLI (`claude -p`), vanilla HTML/CSS/JS (no frameworks, no build step), GitHub Pages w/ custom domain.

---

## File Structure (locked in before tasks)

```
theworstaistudioever/
├── .gitignore                      # node_modules, .run.lock, _test/, .env
├── .env.example                    # NTFY_TOPIC documentation
├── README.md                       # how to run, add seeds, inspect logs, migrate
├── CLAUDE.md                       # repo-scoped conventions for any agent here
├── pipeline.md                     # THE prompt — passed to `claude -p`
├── seeds/
│   ├── companies.json              # ≥100 capitalized famous-startup names
│   ├── subjects.json               # ≥100 lowercase noun phrases
│   ├── companies_test.json         # 5 entries — test/dry-run only
│   └── subjects_test.json          # 5 entries — test/dry-run only
├── state/
│   ├── history.json                # append-only ledger; starts as `[]`
│   └── runs/
│       └── .gitkeep
├── site/                           # GH Pages root (Pages source = /site on main)
│   ├── CNAME                       # contents: theworstaistudioever.com
│   ├── index.html                  # carousel gallery; regenerated each run
│   ├── styles.css                  # gallery shell — STABLE, not touched by daily run
│   ├── 404.html                    # branded 404
│   └── entries/                    # one folder per daily entry (slug = URL)
│       └── .gitkeep
├── scripts/
│   ├── run-daily.sh                # cron entrypoint; wraps claude -p
│   ├── test-pipeline.sh            # dry-run against seeds_test.json
│   └── validate-entry.sh           # post-build HTML + JSON sanity check
└── docs/superpowers/
    ├── specs/2026-05-13-theworstaistudioever-design.md   # already exists
    └── plans/2026-05-13-theworstaistudioever.md          # this file
```

**Boundary rules:**
- `pipeline.md` is the single source of truth for the daily run's logic. The wrapper script is dumb.
- The agent **never** runs `git push`. The wrapper does git operations only after the agent exits 0 and validation passes.
- `site/styles.css` belongs to the gallery shell only. Per-entry pages are self-contained and inline their own styles.
- `state/` is mutated by the agent. `seeds/` is mutated only by humans.

---

## Task 1: Initialize repo + skeleton

**Files:**
- Create: `/home/mitch/github/theworstaistudioever/.gitignore`
- Create: `/home/mitch/github/theworstaistudioever/.env.example`
- Create: `/home/mitch/github/theworstaistudioever/README.md`
- Create: `/home/mitch/github/theworstaistudioever/CLAUDE.md`
- Create: `/home/mitch/github/theworstaistudioever/state/history.json`
- Create: `/home/mitch/github/theworstaistudioever/state/runs/.gitkeep`
- Create: `/home/mitch/github/theworstaistudioever/site/entries/.gitkeep`
- Create: `/home/mitch/github/theworstaistudioever/site/CNAME`

- [ ] **Step 1: Initialize git repo**

```bash
cd /home/mitch/github/theworstaistudioever
git init -b main
```

Expected: `Initialized empty Git repository in /home/mitch/github/theworstaistudioever/.git/`

- [ ] **Step 2: Create `.gitignore`**

```
.env
.run.lock
_test/
node_modules/
.DS_Store
*.swp
```

- [ ] **Step 3: Create `.env.example`**

```
# Required: ntfy.sh topic for failure notifications
# Pick something unguessable; subscribe to it on your phone via the ntfy app
NTFY_TOPIC=theworstaistudioever-CHANGEME

# Optional: override default crontab time (UTC). Default: 14:00 UTC daily.
# CRON_TIME="0 14 * * *"
```

- [ ] **Step 4: Create `site/CNAME`**

File contents (single line, no trailing newline beyond what your editor adds):
```
theworstaistudioever.com
```

- [ ] **Step 5: Create state placeholders**

```bash
echo '[]' > state/history.json
mkdir -p state/runs site/entries
touch state/runs/.gitkeep site/entries/.gitkeep
```

- [ ] **Step 6: Create `README.md`**

```markdown
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
cp .env.example .env  # edit NTFY_TOPIC
./scripts/run-daily.sh
```

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
```

- [ ] **Step 7: Create `CLAUDE.md`**

```markdown
# theworstaistudioever — agent conventions

If you are an agent working in this repo:

- **The daily run prompt is `pipeline.md`.** It is the source of truth for what gets generated each day. Treat changes to it as critical — they ship to production on the next cron tick.
- **Per-entry pages (`site/entries/<slug>/`) are self-contained.** Inline all CSS and JS. No external CSS frameworks (no Tailwind, no Bootstrap, no CDN imports). No build step.
- **The gallery (`site/index.html` + `site/styles.css`) is the stable meta-site shell.** The daily run regenerates `index.html` but never touches `styles.css`.
- **`state/history.json` is append-only.** Never rewrite prior entries; only append.
- **You do not push to git.** The wrapper script handles git. Make changes to the working tree only.
- **Voice rule:** every piece of user-facing copy commits to the "worst AI studio ever" bit — dry, faux-corporate, deadpan. Never earnest. Run all copy through the `anti-ai-slop` skill.
- **Design rule:** every entry's design direction (style, palette, fonts) must differ from the last 7 entries. Read the last 7 `concept.json` files before picking direction in step 3 of the pipeline.

The spec lives at `docs/superpowers/specs/2026-05-13-theworstaistudioever-design.md`. Read it before making structural changes.
```

- [ ] **Step 8: Initial commit**

```bash
git add .
git commit -m "feat: initialize repo skeleton"
```

Expected: `[main (root-commit) <hash>] feat: initialize repo skeleton`

- [ ] **Step 9: Verify directory state**

Run: `ls -la /home/mitch/github/theworstaistudioever`
Expected: `.git`, `.gitignore`, `.env.example`, `README.md`, `CLAUDE.md`, `docs`, `seeds` (will not exist yet — created next task), `site`, `state` all visible.

Run: `cat /home/mitch/github/theworstaistudioever/state/history.json`
Expected: `[]`

---

## Task 2: Generate seed data (companies + subjects)

This task uses a one-shot `claude -p` call to generate the initial 100+ entries in each seed file. The agent generates, the human reviews and edits, then commits.

**Files:**
- Create: `/home/mitch/github/theworstaistudioever/seeds/companies.json`
- Create: `/home/mitch/github/theworstaistudioever/seeds/subjects.json`
- Create: `/home/mitch/github/theworstaistudioever/seeds/companies_test.json`
- Create: `/home/mitch/github/theworstaistudioever/seeds/subjects_test.json`

- [ ] **Step 1: Generate `companies.json`**

```bash
mkdir -p /home/mitch/github/theworstaistudioever/seeds
cd /home/mitch/github/theworstaistudioever
```

Run:
```bash
claude -p 'Output a JSON array of exactly 120 famous, innovative, well-known startup or tech company names. Mix of:
- Consumer (Tinder, Airbnb, Uber, Spotify, TikTok, Netflix...)
- B2B/enterprise (Palantir, Stripe, Snowflake, Databricks, Datadog...)
- Dev tools (Vercel, Figma, Notion, Linear, GitHub...)
- Crypto/fintech (Coinbase, Robinhood, Plaid...)
- Hardware/AI (Anthropic, OpenAI, Tesla, Boston Dynamics...)
- Mix recent unicorns with classics

Rules:
- Capitalize each name exactly as the brand presents itself (Airbnb not AirBnB; OpenAI not Openai).
- Single names only. No "Inc.", no slogans.
- All real companies a tech-aware reader would recognize.
- No duplicates.

Output: a single JSON array of strings. No commentary, no markdown fence.' > seeds/companies.json
```

Verify it parsed cleanly:
```bash
jq 'length' seeds/companies.json
```
Expected: `120` (or close — ≥100 is the bar)

- [ ] **Step 2: Manually review `seeds/companies.json`**

Open the file. Skim for: weird capitalizations, fake-sounding names, duplicates, anything that doesn't pattern-match as a famous startup. Edit in place to fix. Re-run `jq 'length' seeds/companies.json` after editing to confirm count.

- [ ] **Step 3: Generate `subjects.json`**

```bash
claude -p 'Output a JSON array of exactly 120 lowercase noun phrases that complete the sentence "X for ___". Mix of:
- Animals (dogs, cats, fish, ferrets, octopuses, raccoons...)
- Demographics (introverts, lonely retirees, divorced dads, gen Z, only children...)
- Niche professions (mortuary cosmetologists, ice fishermen, lumberjacks...)
- Abstract concepts (regret, mild disappointment, Sunday nights...)
- Inanimate objects (houseplants, coffee mugs, leftover takeout...)
- Mundane situations (HOA meetings, jury duty, group projects...)

Rules:
- Lowercase, no leading article.
- Grammatically fits "Tinder for {subject}" — usually plural noun phrases, sometimes singular.
- Funny is fine but not crass. Absurd > offensive.
- No duplicates.

Output: a single JSON array of strings. No commentary, no markdown fence.' > seeds/subjects.json
```

Verify:
```bash
jq 'length' seeds/subjects.json
```
Expected: `120` (or close — ≥100 is the bar)

- [ ] **Step 4: Manually review `seeds/subjects.json`**

Same review process. Edit in place. Goal: the kind of pairings you'd actually want to see built.

- [ ] **Step 5: Create test seed files (5 entries each)**

```bash
cat > seeds/companies_test.json <<'EOF'
["Tinder", "Palantir", "Airbnb", "Notion", "Figma"]
EOF

cat > seeds/subjects_test.json <<'EOF'
["dogs", "lonely retirees", "houseplants", "HOAs", "jury duty"]
EOF
```

Verify:
```bash
jq 'length' seeds/companies_test.json seeds/subjects_test.json
```
Expected: `5` then `5`.

- [ ] **Step 6: Commit**

```bash
git add seeds/
git commit -m "feat: seed companies + subjects (120 each) + test seeds (5x5)"
```

---

## Task 3: Build validation script (TDD)

The validation script is the gate between the agent exiting 0 and the wrapper committing. If validation fails, no commit happens — the absence of a new entry the next morning is the signal.

**Files:**
- Test: `/home/mitch/github/theworstaistudioever/scripts/test-validate-entry.sh`
- Create: `/home/mitch/github/theworstaistudioever/scripts/validate-entry.sh`

- [ ] **Step 1: Write the failing test harness**

Create `/home/mitch/github/theworstaistudioever/scripts/test-validate-entry.sh`:

```bash
#!/usr/bin/env bash
# Tests for validate-entry.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VALIDATE="$SCRIPT_DIR/validate-entry.sh"
TMP="$(mktemp -d)"
trap "rm -rf $TMP" EXIT

PASS=0
FAIL=0

assert_pass() {
  local name="$1" slug="$2"
  if "$VALIDATE" "$TMP" "$slug" >/dev/null 2>&1; then
    echo "PASS: $name"
    PASS=$((PASS + 1))
  else
    echo "FAIL: $name (expected pass, got fail)"
    FAIL=$((FAIL + 1))
  fi
}

assert_fail() {
  local name="$1" slug="$2"
  if "$VALIDATE" "$TMP" "$slug" >/dev/null 2>&1; then
    echo "FAIL: $name (expected fail, got pass)"
    FAIL=$((FAIL + 1))
  else
    echo "PASS: $name"
    PASS=$((PASS + 1))
  fi
}

make_valid_entry() {
  local slug="$1"
  mkdir -p "$TMP/entries/$slug"
  # ~3KB of real-looking HTML
  printf '<!doctype html><html><head><title>Test</title></head><body>%s</body></html>' \
    "$(head -c 3000 < /dev/urandom | base64 | tr -d '\n' | head -c 3000)" \
    > "$TMP/entries/$slug/index.html"
  cp "$TMP/entries/$slug/index.html" "$TMP/entries/$slug/demo.html"
  cat > "$TMP/entries/$slug/concept.json" <<JSON
{
  "date": "2026-05-13",
  "tagline": "Tinder for dogs",
  "product_name": "Bark",
  "one_liner": "swipe right on good boys",
  "design_direction": {"style":"brutalist","palette":{},"fonts":{},"archetype":"saas-landing"}
}
JSON
}

# Test 1: valid entry passes
make_valid_entry "tinder-for-dogs"
assert_pass "valid entry" "tinder-for-dogs"

# Test 2: missing index.html fails
mkdir -p "$TMP/entries/missing-index"
touch "$TMP/entries/missing-index/demo.html"
echo '{}' > "$TMP/entries/missing-index/concept.json"
assert_fail "missing index.html" "missing-index"

# Test 3: tiny HTML (<2KB) fails
mkdir -p "$TMP/entries/tiny"
echo "<html></html>" > "$TMP/entries/tiny/index.html"
echo "<html></html>" > "$TMP/entries/tiny/demo.html"
echo '{"date":"x","tagline":"x","product_name":"x","one_liner":"x","design_direction":{}}' \
  > "$TMP/entries/tiny/concept.json"
assert_fail "tiny html under 2KB" "tiny"

# Test 4: malformed JSON fails
make_valid_entry "bad-json"
echo "not json" > "$TMP/entries/bad-json/concept.json"
assert_fail "malformed concept.json" "bad-json"

# Test 5: concept.json missing required field fails
make_valid_entry "missing-field"
echo '{"tagline":"x"}' > "$TMP/entries/missing-field/concept.json"
assert_fail "concept.json missing required field" "missing-field"

# Test 6: HTML missing <body> fails
mkdir -p "$TMP/entries/no-body"
printf '<!doctype html><html><head><title>x</title></head></html>%s' \
  "$(head -c 3000 < /dev/urandom | base64 | tr -d '\n' | head -c 3000)" \
  > "$TMP/entries/no-body/index.html"
cp "$TMP/entries/no-body/index.html" "$TMP/entries/no-body/demo.html"
echo '{"date":"x","tagline":"x","product_name":"x","one_liner":"x","design_direction":{}}' \
  > "$TMP/entries/no-body/concept.json"
assert_fail "html missing body tag" "no-body"

echo ""
echo "Results: $PASS passed, $FAIL failed"
[[ $FAIL -eq 0 ]]
```

```bash
chmod +x /home/mitch/github/theworstaistudioever/scripts/test-validate-entry.sh
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `/home/mitch/github/theworstaistudioever/scripts/test-validate-entry.sh`
Expected: fails with `validate-entry.sh: No such file or directory` or similar — script doesn't exist yet.

- [ ] **Step 3: Write `validate-entry.sh`**

Create `/home/mitch/github/theworstaistudioever/scripts/validate-entry.sh`:

```bash
#!/usr/bin/env bash
# Usage: validate-entry.sh <site-root> <slug>
# Exits 0 if entry passes all checks, non-zero with a stderr message otherwise.
set -euo pipefail

if [[ $# -ne 2 ]]; then
  echo "usage: $0 <site-root> <slug>" >&2
  exit 2
fi

SITE_ROOT="$1"
SLUG="$2"
DIR="$SITE_ROOT/entries/$SLUG"

fail() { echo "validate-entry [$SLUG]: $*" >&2; exit 1; }

[[ -d "$DIR" ]] || fail "entry directory missing: $DIR"

# 1. Required files exist
for f in index.html demo.html concept.json; do
  [[ -f "$DIR/$f" ]] || fail "missing required file: $f"
done

# 2. HTML files are >= 2KB
for f in index.html demo.html; do
  size=$(wc -c < "$DIR/$f")
  [[ "$size" -ge 2048 ]] || fail "$f too small: ${size} bytes (need >= 2048)"
done

# 3. HTML files have <html>, </html>, and non-empty <body>
for f in index.html demo.html; do
  grep -qi '<html' "$DIR/$f" || fail "$f missing <html> tag"
  grep -qi '</html>' "$DIR/$f" || fail "$f missing </html> tag"
  grep -qi '<body' "$DIR/$f" || fail "$f missing <body> tag"
done

# 4. concept.json parses
jq empty "$DIR/concept.json" 2>/dev/null || fail "concept.json is not valid JSON"

# 5. concept.json has required top-level fields
for field in date tagline product_name one_liner design_direction; do
  has=$(jq --arg f "$field" 'has($f)' "$DIR/concept.json")
  [[ "$has" == "true" ]] || fail "concept.json missing required field: $field"
done

echo "validate-entry [$SLUG]: OK"
```

```bash
chmod +x /home/mitch/github/theworstaistudioever/scripts/validate-entry.sh
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `/home/mitch/github/theworstaistudioever/scripts/test-validate-entry.sh`
Expected:
```
PASS: valid entry
PASS: missing index.html
PASS: tiny html under 2KB
PASS: malformed concept.json
PASS: concept.json missing required field
PASS: html missing body tag

Results: 6 passed, 0 failed
```

- [ ] **Step 5: Commit**

```bash
git add scripts/validate-entry.sh scripts/test-validate-entry.sh
git commit -m "feat: validate-entry.sh + tests (TDD)"
```

---

## Task 4: Build the gallery shell

The carousel is the stable meta-site surface. The daily run regenerates `site/index.html` from `state/history.json` + per-entry `concept.json` files, but `site/styles.css` stays put. We hand-write both initially so the empty-state works before any entries exist.

**Files:**
- Create: `/home/mitch/github/theworstaistudioever/site/index.html`
- Create: `/home/mitch/github/theworstaistudioever/site/styles.css`
- Create: `/home/mitch/github/theworstaistudioever/site/404.html`

- [ ] **Step 1: Create `site/styles.css`**

```css
:root {
  --bg: #0a0a0a;
  --ink: #f5f5f5;
  --muted: #7a7a7a;
  --accent: #ff3b30;
  --serif: "Times New Roman", Georgia, serif;
  --sans: -apple-system, "Helvetica Neue", Helvetica, Arial, sans-serif;
  --mono: ui-monospace, Menlo, monospace;
}

* { box-sizing: border-box; }
html, body { margin: 0; padding: 0; height: 100%; background: var(--bg); color: var(--ink); font-family: var(--sans); }
a { color: inherit; }

.site-header {
  position: fixed; top: 0; left: 0; right: 0;
  display: flex; justify-content: space-between; align-items: center;
  padding: 1rem 1.5rem; z-index: 10;
  font-family: var(--mono); font-size: 0.8rem; letter-spacing: 0.05em;
  text-transform: uppercase; mix-blend-mode: difference; color: white;
}

.site-header .brand { font-weight: 700; }
.site-header .count { color: var(--muted); }

.carousel {
  height: 100vh; width: 100vw; overflow: hidden; position: relative;
}
.carousel-track {
  display: flex; height: 100%; transition: transform 0.6s cubic-bezier(0.7, 0, 0.2, 1);
  will-change: transform;
}
.slide {
  flex: 0 0 100%; height: 100%;
  display: flex; flex-direction: column; justify-content: center; align-items: center;
  padding: 4rem 2rem; text-align: center;
  position: relative; overflow: hidden;
}
.slide-tagline {
  font-family: var(--serif); font-size: clamp(2.5rem, 8vw, 6rem); line-height: 1.05;
  margin: 0 0 1.5rem; max-width: 18ch; font-style: italic;
}
.slide-blurb {
  font-size: 1.1rem; max-width: 50ch; margin: 0 0 2rem; opacity: 0.9;
}
.slide-cta {
  display: inline-block; padding: 0.85rem 1.6rem;
  border: 1px solid currentColor; border-radius: 999px;
  text-decoration: none; font-family: var(--mono); font-size: 0.85rem;
  letter-spacing: 0.1em; text-transform: uppercase;
  transition: background 0.2s, color 0.2s;
}
.slide-cta:hover { background: currentColor; }
.slide-cta:hover span { color: var(--bg); }
.slide-date {
  position: absolute; bottom: 2rem; left: 50%; transform: translateX(-50%);
  font-family: var(--mono); font-size: 0.75rem; opacity: 0.5;
}

.empty {
  display: flex; height: 100vh; flex-direction: column;
  justify-content: center; align-items: center; text-align: center;
  padding: 2rem;
}
.empty h1 { font-family: var(--serif); font-style: italic; font-size: clamp(2rem, 6vw, 4rem); margin: 0; }
.empty p { color: var(--muted); margin-top: 1rem; max-width: 40ch; }

.nav {
  position: fixed; bottom: 2rem; left: 50%; transform: translateX(-50%);
  display: flex; gap: 0.5rem; align-items: center;
  z-index: 10;
}
.nav button {
  background: transparent; border: 1px solid var(--ink); color: var(--ink);
  width: 2.5rem; height: 2.5rem; border-radius: 50%; cursor: pointer;
  font-family: var(--mono); font-size: 1rem;
  transition: background 0.2s, color 0.2s;
}
.nav button:hover { background: var(--ink); color: var(--bg); }
.dots { display: flex; gap: 0.35rem; padding: 0 1rem; }
.dot { width: 6px; height: 6px; border-radius: 50%; background: var(--muted); cursor: pointer; transition: background 0.2s; }
.dot.active { background: var(--ink); }
```

- [ ] **Step 2: Create empty-state `site/index.html`**

This is the initial empty-state version. The daily run replaces this file entirely once entries exist.

```html
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>theworstaistudioever</title>
  <meta name="description" content="A new mock startup, every day. Mostly bad. Occasionally redeeming.">
  <meta property="og:title" content="theworstaistudioever">
  <meta property="og:description" content="A new mock startup, every day. Mostly bad. Occasionally redeeming.">
  <meta property="og:type" content="website">
  <meta property="og:url" content="https://theworstaistudioever.com">
  <link rel="stylesheet" href="/styles.css">
</head>
<body>
  <header class="site-header">
    <div class="brand">theworstaistudioever</div>
    <div class="count">0 startups · since 2026</div>
  </header>
  <main class="empty">
    <h1>Nothing here yet.</h1>
    <p>A new mock startup ships every day at 14:00 UTC. Come back tomorrow.</p>
  </main>
</body>
</html>
```

- [ ] **Step 3: Create `site/404.html`**

```html
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>404 · theworstaistudioever</title>
  <link rel="stylesheet" href="/styles.css">
</head>
<body>
  <main class="empty">
    <h1>That startup got shut down.</h1>
    <p>The runway didn't extend. The metrics didn't compound. The category was crowded.</p>
    <p><a href="/">← back to the gallery</a></p>
  </main>
</body>
</html>
```

- [ ] **Step 4: Local preview**

```bash
cd /home/mitch/github/theworstaistudioever/site
python3 -m http.server 4173 &
SERVER_PID=$!
```

Open `http://localhost:4173` in a browser. Expected: black background, "theworstaistudioever" header top-left, "Nothing here yet." centered. No console errors.

```bash
kill $SERVER_PID
```

- [ ] **Step 5: Commit**

```bash
cd /home/mitch/github/theworstaistudioever
git add site/
git commit -m "feat: gallery shell + 404 + empty-state index"
```

---

## Task 5: Write `pipeline.md` (THE prompt)

This is the most important file in the repo. It is the literal text passed to `claude -p` each day. Changes to it = changes to production behavior on the next cron tick.

**Files:**
- Create: `/home/mitch/github/theworstaistudioever/pipeline.md`

- [ ] **Step 1: Create `pipeline.md` with the full pipeline prompt**

```markdown
# Daily run — theworstaistudioever

You are the agent responsible for shipping today's daily startup prototype to theworstaistudioever.com. You will execute the 8 steps below in order. Do not skip steps. Do not invent additional steps. The wrapper script will handle git after you exit — do NOT run git commands yourself.

The current working directory is the repo root. All paths are relative to it.

---

## Voice (load this into your bones before generating any copy)

The brand is **"the worst AI studio ever"** — every startup we generate is deadpan, faux-corporate, slightly broken, but committed to the bit. Hero copy reads like a sincere founder pitch that hasn't quite landed. Pricing tiers are absurd, priced with confidence. Testimonials are fake quotes from named "users" with overly specific titles. Nothing is winking-at-the-camera; everything is straight-faced.

Earnest startup tone kills the joke. Never write "Welcome to the future of X." Never write "We're on a mission to..." Never use the word "revolutionize" or "seamless" or "delight" or "empower" sincerely. If you catch yourself writing those, you are off-brand.

**You MUST invoke the `anti-ai-slop` skill before producing any visible copy in steps 2, 4, and 5.** This is not optional.

---

## Step 1 — ROLL

1. Read `seeds/companies.json`, `seeds/subjects.json`, `state/history.json`.
2. Build a deterministic PRNG seeded from today's UTC date string (`YYYY-MM-DD`). Use a simple hash like:
   - Sum the char codes of the date string, multiply by a prime, mod 2^31. Use that as the initial seed for a linear-congruential generator. (Or any PRNG that's deterministic from a string seed.)
3. Draw a random index for `companies` and another for `subjects`. Build candidate pair `{company, subject}`.
4. Check if `{company, subject}` already exists in `state/history.json` (match on both fields). If yes, draw the next pair from the same PRNG. Retry up to 20 times.
5. If 20 retries all hit existing pairs: print `EXHAUSTED: all rolled pairs already in history. add more seeds.` and exit with status 1. Do nothing else.
6. Compute the slug: `slugify(company) + "-for-" + slugify(subject)`, where `slugify(s)` lowercases, replaces any run of non-`[a-z0-9]` with `-`, and trims leading/trailing `-`.
   - Example: `"Y Combinator"` + `"lonely retirees"` → `y-combinator-for-lonely-retirees`.
7. Hold `{company, subject, slug, tagline: "{Company} for {subject}"}` in memory for the rest of the run.

---

## Step 2 — CONCEPT

1. **Invoke the `anti-ai-slop` skill.**
2. Generate a concept for the tagline. Be specific. The fake startup should have a real-sounding product name (not "BarkMatch" — try "Howl", "Heel.", "Sniffr"), a one-liner that commits to the bit, three features that are clearly the wrong solution to the wrong problem (but pitched seriously), three pricing tiers with deadpan absurd names and confident prices, and three testimonials from named fictional users with overly specific titles.
3. Also describe what the **one interactive demo screen** will show. Be concrete: "a swipeable card stack of golden retrievers with verified-vaccination badges and a 'cuddle compatibility' score from 1-10" — not "the main product UI."
4. Build the concept JSON object (you'll write it to disk in step 3 alongside the design direction). Required fields:
   ```
   {
     "date": "YYYY-MM-DD",          // today's UTC date
     "company": "Tinder",            // from step 1
     "subject": "dogs",              // from step 1
     "tagline": "Tinder for dogs",
     "slug": "tinder-for-dogs",
     "product_name": "...",
     "one_liner": "...",
     "brand_voice_notes": "...",
     "hero": { "h1": "...", "sub": "...", "primary_cta": "..." },
     "features": [
       { "title": "...", "blurb": "..." },
       { "title": "...", "blurb": "..." },
       { "title": "...", "blurb": "..." }
     ],
     "pricing_tiers": [
       { "name": "...", "price": "...", "tagline": "...", "perks": ["...","..."] },
       { "name": "...", "price": "...", "tagline": "...", "perks": ["...","..."] },
       { "name": "...", "price": "...", "tagline": "...", "perks": ["...","..."] }
     ],
     "testimonials": [
       { "quote": "...", "name": "...", "title": "..." },
       { "quote": "...", "name": "...", "title": "..." },
       { "quote": "...", "name": "...", "title": "..." }
     ],
     "demo_screen_concept": "..."
   }
   ```

---

## Step 3 — PLAN (visual direction)

1. **Invoke the `ui-ux-pro-max` skill.** Use it to select:
   - **style archetype** (e.g. brutalist, claymorphic, bento, editorial, glassmorphism, neumorphism, skeuomorphic, flat, swiss-modernist, magazine, retro-futurist, etc.)
   - **palette** — pick one from its 161-palette library, or derive a custom one. Provide hex values for `primary`, `accent`, `bg`, `fg`, `muted`, `ink`.
   - **font pairing** — pick from its 57 pairings. Provide `display` and `body` font-family stacks.
   - **product-type archetype** for the landing page composition.

2. **Anti-sameness check.** Read the last 7 entries' `concept.json` files in `site/entries/*/concept.json` (most recent 7 by date). The (style, palette name, fonts pair) tuple you select **must not match** any of the last 7. If your initial pick collides, reselect.

3. Append the `design_direction` object to the concept JSON in memory:
   ```
   "design_direction": {
     "style": "...",
     "palette": { "primary": "#...", "accent": "#...", "bg": "#...", "fg": "#...", "muted": "#...", "ink": "#..." },
     "fonts": { "display": "...", "body": "..." },
     "archetype": "...",
     "motion_vocab": "...",
     "hero_composition_notes": "..."
   }
   ```

4. Write the full concept JSON to `site/entries/<slug>/concept.json`. Use `mkdir -p` to create the entry directory.

---

## Step 4 — BUILD LANDING

1. **Invoke the `frontend-design` skill.** This is required — it's the guardrail against generic AI output.
2. Write a single self-contained HTML file to `site/entries/<slug>/index.html` with:
   - `<head>`: title (`product_name · theworstaistudioever`), meta description (the one-liner), Open Graph tags, the chosen Google Fonts import (if any) inline.
   - `<style>` block: inline CSS implementing the chosen style + palette + fonts. No external CSS frameworks. No Tailwind CDN. No Bootstrap.
   - `<body>`: hero, features (3), testimonials (3), pricing (3), footer with small "← theworstaistudioever" link to `/`, and a prominent "open the demo →" CTA linking to `./demo.html`.
   - Any JS needed (smooth scroll, etc.) inline in a `<script>` tag.
3. All visible copy passes through `anti-ai-slop` voice rules. No generic AI tells.
4. The page should look like a real, well-funded startup's landing page in the chosen style — not a template.

---

## Step 5 — BUILD DEMO

1. Write `site/entries/<slug>/demo.html` — a single self-contained HTML file containing one interactive screen of the imagined product, populated with fake data.
2. Inherits the palette and typography from step 3, but uses **product-UI layout** (not marketing). Think: a dashboard, a feed, a swipe-stack, a settings page, a config editor — whatever fits the `demo_screen_concept` from step 2.
3. Real interactivity where cheap (vanilla JS, no frameworks): filtering, toggling, modal open/close, drag-reorder, tab switching, fake search. No real API calls — mock everything client-side.
4. Top-left chrome: small back link "← back to the pitch" to `./index.html`.
5. Use `frontend-design` skill while building. Run all visible copy through `anti-ai-slop`.

---

## Step 6 — GALLERY REBUILD

1. Read every `site/entries/*/concept.json`.
2. Sort by `date` descending (newest first).
3. Regenerate `site/index.html` from scratch. Replace the entire file. The new file:
   - Uses the existing `<link rel="stylesheet" href="/styles.css">` — do NOT inline gallery styles.
   - Includes the standard `<head>` (title, meta, og tags) and `<header class="site-header">`.
   - Renders one `<section class="slide">` per entry inside a `<div class="carousel-track">`. Each slide:
     - Background: a subtle radial gradient or solid color derived from the entry's `palette.bg`.
     - Text color: `palette.ink` (with fallback to `--ink`).
     - Tagline as `.slide-tagline` (italic serif).
     - The entry's `hero.sub` (or `one_liner`) as `.slide-blurb`.
     - A `.slide-cta` link to `/entries/<slug>/`.
     - `.slide-date` showing the formatted date.
   - Includes a small `<nav class="nav">` with `←` `→` buttons and clickable `.dots`.
   - Includes a `<script>` block (inlined, not external) that wires up:
     - Click `→` advances slide (translateX the track).
     - Click `←` retreats.
     - `ArrowLeft` / `ArrowRight` keyboard nav.
     - Click a dot jumps to that slide.
     - Touch swipe nav (basic, vanilla — track `touchstart` / `touchend`, threshold ~50px).
   - Updates the header count: `N startups · since 2026`.

---

## Step 7 — VALIDATE & RECORD

1. Run `scripts/validate-entry.sh site <slug>` via the Bash tool. If it exits non-zero, abort the run — print the error, do not proceed.
2. Append `{date, company, subject, slug}` to `state/history.json`. Read the existing array, append, write back. Maintain JSON validity.
3. Write a run summary to `state/runs/<today>.log`. Include:
   - What was rolled (company, subject, slug).
   - Number of rerolls.
   - Design direction chosen (style, palette, fonts).
   - Any warnings or near-misses.
   - Confirmation that validation passed.

---

## Step 8 — DONE

Print exactly this line to stdout (the wrapper greps for it):

```
RUN_COMPLETE: <slug>
```

Then exit cleanly. **Do NOT run git commands.** The wrapper handles git.

---

## Things to NOT do

- Do not introduce any build step. No npm install. No bundlers.
- Do not use external CSS frameworks (Tailwind, Bootstrap) in per-entry pages.
- Do not write any file outside the working tree.
- Do not commit, push, or pull.
- Do not skip skill invocations to "save time."
- Do not pick a style/palette/fonts tuple that matches any of the last 7 entries.
- Do not earnestly pitch the startup. Commit to the bit.
```

- [ ] **Step 2: Verify file exists and is sane**

Run: `wc -l /home/mitch/github/theworstaistudioever/pipeline.md`
Expected: roughly 180-220 lines.

Run: `head -5 /home/mitch/github/theworstaistudioever/pipeline.md`
Expected: `# Daily run — theworstaistudioever` then the opening paragraph.

- [ ] **Step 3: Commit**

```bash
cd /home/mitch/github/theworstaistudioever
git add pipeline.md
git commit -m "feat: pipeline.md — the daily run prompt"
```

---

## Task 6: Build `run-daily.sh` wrapper

The wrapper is the cron entrypoint. It locks, pulls, runs the agent, validates, commits, pushes, and notifies on failure.

**Files:**
- Create: `/home/mitch/github/theworstaistudioever/scripts/run-daily.sh`

- [ ] **Step 1: Write `run-daily.sh`**

```bash
#!/usr/bin/env bash
# Daily cron entrypoint for theworstaistudioever.
# - Single-instance lock
# - Pulls latest
# - Runs `claude -p < pipeline.md`
# - Wrapper does git (agent never has push perms)
# - Notifies via ntfy.sh on failure
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

# Load .env if present
if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

DATE_UTC="$(date -u +%F)"
LOG="state/runs/${DATE_UTC}.log"
mkdir -p "$(dirname "$LOG")"

# Single-instance lock — if another invocation is running, exit cleanly
exec 9>".run.lock"
if ! flock -n 9; then
  echo "[$(date -u)] another run in progress — exiting" >> "$LOG"
  exit 0
fi

log() { echo "[$(date -u +%FT%TZ)] $*" | tee -a "$LOG"; }

notify_fail() {
  local msg="$1"
  if [[ -n "${NTFY_TOPIC:-}" ]]; then
    curl -fsSL -X POST \
      -H "Title: theworstaistudioever cron failed" \
      -d "${msg}. See ${LOG}" \
      "https://ntfy.sh/${NTFY_TOPIC}" >/dev/null 2>&1 || true
  fi
}

log "=== daily run start ==="

# Pull latest in case seeds or pipeline changed elsewhere
if ! git pull --rebase --autostash >> "$LOG" 2>&1; then
  log "git pull failed — continuing anyway"
fi

# Snapshot the entries directory before the run, so we know which slug got created
BEFORE_ENTRIES=$(ls site/entries 2>/dev/null | sort || true)

# Run the agent
log "invoking claude -p"
if ! claude -p "$(cat pipeline.md)" \
      --allowed-tools "Read,Write,Edit,Glob,Grep,Bash(jq:*),Bash(node:*),Bash(ls:*),Bash(cat:*),Bash(mkdir:*),Skill" \
      --max-turns 80 \
      >> "$LOG" 2>&1; then
  log "RUN FAILED: claude -p exited non-zero"
  notify_fail "claude -p exited non-zero"
  exit 1
fi

# Check that the agent printed RUN_COMPLETE
if ! grep -q "^RUN_COMPLETE:" "$LOG"; then
  log "RUN FAILED: agent did not print RUN_COMPLETE marker"
  notify_fail "agent did not signal completion"
  exit 1
fi

# Figure out which slug got created
AFTER_ENTRIES=$(ls site/entries 2>/dev/null | sort || true)
NEW_SLUG=$(comm -13 <(echo "$BEFORE_ENTRIES") <(echo "$AFTER_ENTRIES") | head -1)

if [[ -z "$NEW_SLUG" ]]; then
  log "RUN FAILED: no new entry directory created"
  notify_fail "no new entry produced"
  exit 1
fi

log "new entry: $NEW_SLUG"

# Validate the new entry
if ! ./scripts/validate-entry.sh site "$NEW_SLUG" >> "$LOG" 2>&1; then
  log "RUN FAILED: validate-entry rejected $NEW_SLUG"
  notify_fail "validation failed for $NEW_SLUG"
  exit 1
fi

# Commit + push (wrapper, not agent)
TAGLINE=$(jq -r '.tagline' "site/entries/$NEW_SLUG/concept.json")
log "committing: $TAGLINE"

git add . >> "$LOG" 2>&1

# If nothing actually changed in tracked files, log + bail
if git diff --cached --quiet; then
  log "nothing staged — exiting cleanly"
  exit 0
fi

git commit -m "feat: ${TAGLINE}" >> "$LOG" 2>&1

# Push with 3 retries
for i in 1 2 3; do
  if git push >> "$LOG" 2>&1; then
    log "pushed"
    break
  fi
  log "push attempt $i failed; sleeping"
  sleep $((i * 5))
  if [[ "$i" == "3" ]]; then
    log "RUN FAILED: push failed after 3 attempts"
    notify_fail "git push failed after 3 attempts"
    exit 1
  fi
done

log "=== daily run complete: $TAGLINE ==="
```

```bash
chmod +x /home/mitch/github/theworstaistudioever/scripts/run-daily.sh
```

- [ ] **Step 2: Lint the script**

```bash
bash -n /home/mitch/github/theworstaistudioever/scripts/run-daily.sh
```
Expected: no output (syntax OK).

If `shellcheck` is installed:
```bash
shellcheck /home/mitch/github/theworstaistudioever/scripts/run-daily.sh
```
Expected: no errors. Warnings about unbound vars in optional .env load are OK.

- [ ] **Step 3: Commit**

```bash
cd /home/mitch/github/theworstaistudioever
git add scripts/run-daily.sh
git commit -m "feat: run-daily.sh wrapper with lock + notify"
```

---

## Task 7: Build `test-pipeline.sh` (dry-run harness)

`test-pipeline.sh` runs the full pipeline against `seeds_test.json` (5×5) into a sandbox `_test/` subtree. Never commits. Used to validate prompt changes.

**Files:**
- Create: `/home/mitch/github/theworstaistudioever/scripts/test-pipeline.sh`

- [ ] **Step 1: Write `test-pipeline.sh`**

```bash
#!/usr/bin/env bash
# Dry-run the daily pipeline against test seeds into a sandbox subtree.
# Does NOT commit. Does NOT touch real state. Safe to run repeatedly.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

SANDBOX="_test"
rm -rf "$SANDBOX"
mkdir -p "$SANDBOX/seeds" "$SANDBOX/state/runs" "$SANDBOX/site/entries"
cp seeds/companies_test.json "$SANDBOX/seeds/companies.json"
cp seeds/subjects_test.json "$SANDBOX/seeds/subjects.json"
echo '[]' > "$SANDBOX/state/history.json"
cp site/styles.css "$SANDBOX/site/styles.css"
cp site/404.html "$SANDBOX/site/404.html"
cp site/CNAME "$SANDBOX/site/CNAME"

LOG="$SANDBOX/run.log"

# Build a test prompt by replacing relative paths inside pipeline.md
# (The pipeline already uses repo-root-relative paths; we just `cd` into the sandbox)
cd "$SANDBOX"
cp ../pipeline.md ./pipeline.md

echo "=== dry run start ==="
if ! claude -p "$(cat pipeline.md)" \
      --allowed-tools "Read,Write,Edit,Glob,Grep,Bash(jq:*),Bash(node:*),Bash(ls:*),Bash(cat:*),Bash(mkdir:*),Skill" \
      --max-turns 80 \
      2>&1 | tee "../$LOG" >&2; then
  echo "DRY RUN FAILED — see $LOG"
  exit 1
fi

cd ..

# Validate whatever entry got produced
NEW_SLUG=$(ls "$SANDBOX/site/entries" 2>/dev/null | head -1)
if [[ -z "$NEW_SLUG" ]]; then
  echo "DRY RUN FAILED — no entry created"
  exit 1
fi

if ! ./scripts/validate-entry.sh "$SANDBOX/site" "$NEW_SLUG"; then
  echo "DRY RUN FAILED — validation rejected $NEW_SLUG"
  exit 1
fi

echo ""
echo "=== dry run complete ==="
echo "Output: $SANDBOX/site/entries/$NEW_SLUG/"
echo "Preview:"
echo "  cd $SANDBOX/site && python3 -m http.server 4173"
echo "  open http://localhost:4173/entries/$NEW_SLUG/"
```

```bash
chmod +x /home/mitch/github/theworstaistudioever/scripts/test-pipeline.sh
```

- [ ] **Step 2: Lint**

```bash
bash -n /home/mitch/github/theworstaistudioever/scripts/test-pipeline.sh
```
Expected: no output.

- [ ] **Step 3: Ensure `_test/` is git-ignored**

`.gitignore` (from Task 1) already includes `_test/`. Verify:
```bash
grep '_test/' /home/mitch/github/theworstaistudioever/.gitignore
```
Expected: `_test/`

- [ ] **Step 4: Commit**

```bash
cd /home/mitch/github/theworstaistudioever
git add scripts/test-pipeline.sh
git commit -m "feat: test-pipeline.sh dry-run harness"
```

---

## Task 8: First dry run + iterate on `pipeline.md`

This is the gut-check. Run the full pipeline against test seeds, inspect the output, refine the prompt.

**Files:**
- Possibly modify: `/home/mitch/github/theworstaistudioever/pipeline.md` (based on findings)

- [ ] **Step 1: Run the dry-run harness**

```bash
cd /home/mitch/github/theworstaistudioever
./scripts/test-pipeline.sh
```

Expected: `=== dry run complete ===` with a slug printed and a preview command.

If it failed: read `_test/run.log`, identify which step broke, edit `pipeline.md` to clarify, re-run.

- [ ] **Step 2: Preview the output**

```bash
cd _test/site
python3 -m http.server 4173 &
PREVIEW_PID=$!
```

Open `http://localhost:4173/entries/<slug>/` in a browser.

Check:
- Does it look like a real, well-funded startup landing page in a specific style?
- Is the copy on-brand (deadpan, faux-corporate, never earnest)?
- Does the "open the demo →" CTA work?
- Does the demo page have real interactivity (not just static mocks)?
- Does the back-link from demo work?

```bash
kill $PREVIEW_PID
```

- [ ] **Step 3: Iterate on `pipeline.md`**

Based on what felt off, edit `pipeline.md`. Common adjustments:
- If copy reads too earnest → strengthen the voice section, add specific don't-write phrases.
- If pages look generic → add more specific style/palette examples to step 3, emphasize the anti-sameness check.
- If demo lacks interactivity → add concrete interaction examples to step 5.
- If validation fails on too-small HTML → bump expected page complexity.

Re-run `./scripts/test-pipeline.sh` after each edit. Iterate until ~2 consecutive dry runs produce output you're happy with.

- [ ] **Step 4: Commit prompt refinements (if any)**

```bash
cd /home/mitch/github/theworstaistudioever
git add pipeline.md
git diff --cached --quiet || git commit -m "refactor: tune pipeline.md based on dry-run output"
```

If no changes were needed, skip this step. The commit only happens if there's actually a diff.

---

## Task 9: Push to GitHub + enable Pages + verify domain

**Files:** none (manual GitHub-side configuration)

- [ ] **Step 1: Create the GitHub repo**

You must do this manually (gh CLI works if authenticated):

Option A — `gh` CLI:
```bash
cd /home/mitch/github/theworstaistudioever
gh repo create theworstaistudioever --public --source=. --remote=origin --push
```

Option B — manual:
1. Visit https://github.com/new
2. Repo name: `theworstaistudioever`
3. Public
4. Do NOT initialize with README (we already have files)
5. Create.
6. Then:
```bash
cd /home/mitch/github/theworstaistudioever
git remote add origin git@github.com:<your-username>/theworstaistudioever.git
git push -u origin main
```

Expected: the repo is now on GitHub with all commits visible.

- [ ] **Step 2: Enable GitHub Pages**

In the GitHub repo's web UI:
1. Settings → Pages
2. Source: **Deploy from a branch**
3. Branch: **main**, folder: **`/site`**
4. Save.
5. Custom domain: enter `theworstaistudioever.com`. Save. Enable "Enforce HTTPS" once the cert provisions (~10 min).

- [ ] **Step 3: Point the domain at GitHub Pages**

In your domain registrar's DNS settings for `theworstaistudioever.com`, add:

| Type | Name | Value |
|---|---|---|
| A | `@` | `185.199.108.153` |
| A | `@` | `185.199.109.153` |
| A | `@` | `185.199.110.153` |
| A | `@` | `185.199.111.153` |
| CNAME | `www` | `<your-username>.github.io.` |

Wait 5–60 minutes for DNS propagation.

- [ ] **Step 4: Verify**

```bash
dig +short theworstaistudioever.com
```
Expected: returns one of the 185.199.x.153 IPs.

Visit `https://theworstaistudioever.com`. Expected: black empty-state page "Nothing here yet."

- [ ] **Step 5: Verify push perms work for the wrapper**

The wrapper does `git push`. Ensure your local git is authenticated:
```bash
cd /home/mitch/github/theworstaistudioever
git push  # should be a no-op but exit 0
```
Expected: `Everything up-to-date` or pushes a tiny commit cleanly.

---

## Task 10: First real run + cron installation

Now the real production-equivalent run, against the real 120×120 seeds. Then crontab.

**Files:**
- Modify: user's `crontab -e`
- Create: `/home/mitch/github/theworstaistudioever/.env`

- [ ] **Step 1: Configure `.env`**

```bash
cd /home/mitch/github/theworstaistudioever
cp .env.example .env
```

Edit `.env`. Set `NTFY_TOPIC` to something unguessable, e.g.:
```
NTFY_TOPIC=tws-mitch-9d8f7e6c5b4a3210
```

Install the ntfy app on your phone, subscribe to that topic. Test:
```bash
curl -d "test" "https://ntfy.sh/${NTFY_TOPIC}"
```
Expected: your phone buzzes.

- [ ] **Step 2: First real run, manually**

```bash
cd /home/mitch/github/theworstaistudioever
./scripts/run-daily.sh
```

Expected: completes in 2–5 minutes, commits + pushes a new entry, GH Pages updates within ~60 seconds.

Visit `https://theworstaistudioever.com`. Expected: carousel now shows 1 slide; clicking through shows the landing page.

Inspect:
```bash
cat state/runs/$(date -u +%F).log | tail -50
cat state/history.json
ls site/entries/
```

Expected: log ends cleanly, history.json has 1 entry, one folder in `site/entries/`.

If the run failed: notification fires on phone. Read the log, fix the issue (likely `pipeline.md` tuning or missing tool permission), re-run.

- [ ] **Step 3: Install crontab**

```bash
crontab -e
```

Add:
```
# theworstaistudioever — daily run, 14:00 UTC (= 9am ET, 10am EDT)
0 14 * * *  /home/mitch/github/theworstaistudioever/scripts/run-daily.sh
```

Save and exit.

Verify:
```bash
crontab -l | grep theworstaistudioever
```
Expected: the line you just added.

- [ ] **Step 4: Verify the cron entry runs cleanly via a manual force-fire**

Cron environments are stripped — they don't inherit your shell's PATH. Verify the wrapper survives a clean env:

```bash
env -i HOME="$HOME" PATH="/usr/local/bin:/usr/bin:/bin" \
  /home/mitch/github/theworstaistudioever/scripts/run-daily.sh
```

The lock will likely make this exit cleanly (same-day lock from step 2). Check `state/runs/$(date -u +%F).log` ends with the expected lock-skip message:
```
another run in progress — exiting
```
…or, if step 2 was on a previous calendar day, it'll do a real run.

If it fails because `claude` isn't on PATH in a stripped env:
```bash
which claude
```
…and either symlink it into `/usr/local/bin/` or prepend the correct PATH to the cron line:
```
0 14 * * *  PATH=/home/mitch/.local/bin:/usr/local/bin:/usr/bin:/bin /home/mitch/github/theworstaistudioever/scripts/run-daily.sh
```

- [ ] **Step 5: Commit any cron-related tweaks**

If you had to modify the wrapper to inline a PATH or adjust skill invocation order, commit:
```bash
cd /home/mitch/github/theworstaistudioever
git add scripts/run-daily.sh pipeline.md
git diff --cached --quiet || git commit -m "fix: cron-env compatibility tweaks"
git push
```

---

## Task 11: First-week monitoring + final docs polish

The cron now fires daily. The first week is a manual review window — eyeball each new entry, tune `pipeline.md` based on what's off.

**Files:**
- Possibly modify: `/home/mitch/github/theworstaistudioever/pipeline.md`
- Possibly modify: `/home/mitch/github/theworstaistudioever/README.md`

- [ ] **Step 1: Set a daily reminder for 7 days**

Every morning for the next 7 days, after the 14:00 UTC run:
1. Visit `https://theworstaistudioever.com`. Check the new slide.
2. Click through to the entry.
3. Inspect:
   - Landing copy: on-brand?
   - Visual identity: clearly distinct from yesterday?
   - Demo: actually interactive?
   - 404, footer, back-links: all working?
4. Read `state/runs/<date>.log` end-to-end.

Note anything off in a scratch list.

- [ ] **Step 2: Apply tuning patches**

If after 3–4 days a pattern emerges (e.g. "demos always look like dashboards", "copy keeps drifting earnest by feature 3"), edit `pipeline.md`:

```bash
cd /home/mitch/github/theworstaistudioever
# edit pipeline.md
./scripts/test-pipeline.sh  # validate the change in dry-run
git add pipeline.md
git commit -m "refactor: pipeline tuning — <what you changed>"
git push
```

The change takes effect on the next 14:00 UTC tick.

- [ ] **Step 3: Update README with anything you learned**

If you discovered an operational thing worth documenting (e.g. "if you're running on a laptop that sleeps, use `caffeinate` or move to a VPS"), add a section to `README.md`. Commit.

- [ ] **Step 4: Confirm migration prerequisites are documented**

Open `docs/superpowers/specs/2026-05-13-theworstaistudioever-design.md` section 11. Confirm the local→remote migration steps still match reality (PAT scope, routine prompt body). If anything drifted during implementation, fix the spec.

```bash
cd /home/mitch/github/theworstaistudioever
git add docs/
git diff --cached --quiet || git commit -m "docs: align spec with shipped implementation"
git push
```

- [ ] **Step 5: Done**

The system runs unattended. When quality is consistently good (subjective bar — probably 5+ days you'd genuinely show someone), kick off migration to a `/schedule` routine using the procedure in spec section 11. Or just let the local cron run forever — that's also fine.
