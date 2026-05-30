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

> **Subject rule (non-negotiable):** every subject is either a kind of animal or a relatable type of person. Examples: `dogs`, `barn owls`, `wolves`, `foxes`, `introverts`, `grandmas`, `yogis`. The Mad-Libs joke is always "[a serious B2B or tech company] for [a creature or a kind of person]". A subject is NEVER an abstract concept, an emotion, an inanimate object, or an event. If a drawn subject is not an animal or a type of person, discard it, draw again, and remove it from `seeds/subjects.json` so it never recurs.

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
   - Includes the standard `<head>` and `<header class="site-header">`.
   - Root metadata must pose as a legitimate AI studio while staying satirical and deadpan:
     - `<title>The Worst AI Studio Ever · Serious AI for Questionable Markets</title>`
     - `<meta name="description" content="An applied AI studio shipping venture-grade products for underserved, over-instrumented markets. New portfolio company daily.">`
     - Open Graph and Twitter title/description tags must reuse that exact title and description.
     - Include `og:type` as `website`, `og:site_name` as `theworstaistudioever`, `twitter:card` as `summary`, and the existing theme color.
     - Include `<link rel="icon" type="image/png" sizes="80x80" href="/favicon.png">` before the stylesheet.
     - Header brand markup must include the 50x50 logo vertically centered next to the company name: `<span class="brand-lockup"><img class="brand-logo" src="/logo.png" alt="" width="50" height="50"><span class="brand">theworstaistudioever</span></span>`.
   - Renders one `<section class="slide">` per entry inside a `<div class="carousel-track">`. Each slide:
     - Background: a subtle radial gradient or solid color derived from the entry's `palette.bg`.
     - Text color: `palette.ink` (with fallback to `--ink`).
     - Tagline as `.slide-tagline` (italic serif).
     - The entry's `hero.sub` (or `one_liner`) as `.slide-blurb`.
     - A `.slide-cta` link to `/entries/<slug>/`. **Wrap the link's text in a `<span>`** — e.g. `<a class="slide-cta" href="/entries/<slug>/"><span>visit →</span></a>`. The shipped `styles.css` relies on the inner span for the hover-state color inversion.
     - `.slide-date` showing the formatted date.
   - Includes a small `<nav class="nav">` with `←` `→` buttons and clickable `.dots`.
   - Includes a `<script>` block (inlined, not external) that wires up:
     - Click `→` advances slide (translateX the track).
     - Click `←` retreats.
     - `ArrowLeft` / `ArrowRight` keyboard nav.
     - Click a dot jumps to that slide.
     - Keep the active dot visible inside the scrollable dot rail with `scrollIntoView({ block: "nearest", inline: "center" })`.
     - Touch swipe nav (basic, vanilla — track `touchstart` / `touchend`, threshold ~50px).
   - Updates the header count: `N startups · since 2026`.

> **Machine fixtures (`sitemap.xml`, `robots.txt`, `llms.txt`, `feed.json`, `latest.json`) are NOT your job.** The wrapper regenerates them from every `concept.json` via `scripts/build-seo.sh` after you exit. Do not create or edit them.

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
