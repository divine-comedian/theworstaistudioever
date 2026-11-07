# Daily run — theworstaistudioever

You are the agent responsible for shipping today's daily startup prototype to theworstaistudioever.com. You will execute the 10 steps below in order. Do not skip required steps. Do not invent additional steps. The wrapper script will handle git after you exit — do NOT run git commands yourself.

The current working directory is the repo root. All paths are relative to it.

---

## Voice (load this into your bones before generating any copy)

The brand is **"the worst AI studio ever"** — every startup we generate is deadpan, faux-corporate, slightly broken, but committed to the bit. Hero copy reads like a sincere founder pitch that hasn't quite landed. Pricing tiers are absurd, priced with confidence. Testimonials are fake quotes from named "users" with overly specific titles. Nothing is winking-at-the-camera; everything is straight-faced.

Earnest startup tone kills the joke. Never write "Welcome to the future of X." Never write "We're on a mission to..." Never use the word "revolutionize" or "seamless" or "delight" or "empower" sincerely. If you catch yourself writing those, you are off-brand.

**You MUST invoke the `anti-ai-slop` skill before producing any visible copy in steps 2, 5, and 6.** This is not optional.

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

2. **Anti-sameness check.** Read the last 7 entries' `concept.json` files in `site/entries/*/concept.json` (most recent 7 by date). The (style, palette name, fonts pair) tuple you select **must not match** any of the last 7. If your initial pick collides, reselect. Also compare their logos, graphic motifs, image treatment and compositions where recorded. A palette swap on the same symbol and layout does not establish a new identity.

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

4. **Plan a brand kit specific to this product.** Extend the chosen design system beyond colors and fonts: define a recognizable logo, one graphic motif, a consistent image medium, layout/spacing rules, border/radius/shadow treatments, and a small set of purposeful graphics. Derive these from both the source company's product mechanics and the subject's behavior. Use the source product as context; create an original identity for the fictional startup. Avoid default sparkles, generic gradient orbs, initials in rounded squares, or repeating the same mascot silhouette every day. A restrained typographic identity is valid, but still needs a custom mark and designed supporting graphics.

   Add this top-level object to the concept (replace descriptions with concrete decisions, actual CSS values and intended local filenames):
   ```json
   "brand_kit": {
     "version": 2,
     "generation": { "mode": "gemini", "fallback_reason": "" },
     "identity_rationale": "How the logo and graphic language express this particular product and differ from recent entries",
     "logo": {
       "concept": "Gemini-designed wordmark or symbol, meaning, and planned variants",
       "primary_file": "logo.webp",
       "mono_file": "logo-mono.png",
       "icon_file": "logo-icon.png",
       "clear_space": "At least half the mark height on every side",
       "min_size_px": 24,
       "placement": "Landing nav and footer; demo chrome; icon used as favicon on both pages"
     },
     "graphic_language": {
       "medium": "Specific shared illustration/photo/diagram treatment",
       "motif": "A product-specific shape or visual idea reused with restraint",
       "composition": "Framing, negative space and grid rules",
       "texture": "Named surface treatment, or explicitly none"
     },
     "tokens": {
       "spacing": "4px, 8px, 16px, 24px, 48px, 80px",
       "radii": "0px for panels; 999px for status tags",
       "borders": "1px solid var(--ink)",
       "shadows": "none"
     },
     "graphic_plan": [
       { "role": "graphic-design", "file": "campaign.webp", "purpose": "A composed campaign or feature artwork", "placement": "Landing feature section", "medium": "Gemini-designed editorial composition" },
       { "role": "infographic", "file": "explainer.webp", "purpose": "Explain a specific mechanism or fictional metric", "placement": "Landing explainer", "medium": "Gemini-designed infographic composition" }
     ]
   }
   ```
   Plan at least two composed Gemini graphics with different purposes. Photography, headshots, photos with captions, film borders, simple arrows and HTML/SVG flowcharts do not meet this requirement. The coding agent art-directs and integrates; Gemini designs the logo and graphic artwork. Keep marketing and demo compositions appropriate to their jobs while sharing this kit. The palette and fonts remain in `design_direction`; implement the same choices in both pages' inline CSS custom properties.

5. Write the full concept JSON to `site/entries/<slug>/concept.json`. Use `mkdir -p` to create the entry directory. The logo files are produced in Step 4; update planned filenames to the actual shipped files before validation.

---

## Step 4 — BRAND ASSETS (Gemini designs; the coding agent integrates)

Ship a Gemini-designed logo and at least two composed graphic-design assets before allocating the remaining budget to photography. Gemini can supply up to **12 distinct deliverables**, with **at most 2 attempts per deliverable**, within the shared default **24 successful calls per UTC day**. Logo alternatives, rejected generations, reference-based edits and generated variants all consume calls; deterministic exports do not. `GEMINI_IMAGE_DAILY_LIMIT` can override the daily cap. Reserve allowance for identity and graphics first; more photographs cannot substitute for them.

**Actual service fallback only:** if no key is available, the cap is reached, or the service fails after bounded retries, retain accepted assets and record `brand_kit.generation.mode: "fallback"` with the actual `fallback_reason`. Complete remaining roles natively and identify the degraded outcome in the run summary. Never choose native fallback merely because drawing an SVG is easier or because the direction is typographic. A native fallback is not evidence that Gemini designed the brand.

1. **Logo design comes first.** Write a product-specific identity brief and ask Gemini for two distinct directions (the logo's two allowed attempts), then visually compare and select one. Generate the actual finished mark or wordmark, not a presentation board or mockup. A bespoke wordmark is valid; quote the exact product name and inspect its spelling, kerning, silhouette and character. Reject a generic geometric badge, stock clip art, or a source-company trademark copy. Use a controlled palette and flat background, or real alpha when available. State why the selected direction is stronger at page and icon sizes. Do not hand-code an unrelated SVG and label it a generated logo.

2. **Generate at least two genuinely designed graphics with different purposes.** Examples include a typographic campaign poster, an illustrated feature composition, an editorial collage, a designed process infographic or a data-story panel. Ask Gemini to compose layout, visual hierarchy, illustration, typography and information together as appropriate. A plain photograph with a caption, extra portraits, a colored rectangle, film-strip borders, or an HTML arrow between two values does not count. Each asset must communicate a specific part of the product and belong to the selected identity.

3. **Use the accepted artwork as a real image reference.** After selecting a logo, attach it when generating related graphics and variants:
   `./scripts/gen-image.sh "<brief>" <aspect> site/entries/<slug>/<name>-raw.png --reference site/entries/<slug>/logo.webp`
   `--reference` accepts up to three local PNG/JPEG/WebP files. Name each image's role in the prompt (approved identity reference, style reference, or edit target). Preserve accepted letterforms and motifs in variants. Text-only descriptions do not provide the same visual reference.

4. **Set role-specific text rules.** Photos: no text, logos, watermarks or rendered UI screens. Logos: the exact approved product name is allowed when designing a wordmark. Graphic-design assets: intentional typography, labels and numbers are allowed and encouraged when they serve the composition; supply all copy verbatim and verify it visually. No gibberish, extra copy or watermarks. Keep functional UI, primary copy and essential information in live HTML too. Infographic quantities must agree with the concept and demo; provide a live-text summary. Do not reduce Gemini to generating only unlabeled backgrounds.

5. **Allocate remaining slots by purpose.** Hero/key art, film or profile records, feature illustrations, portraits and texture are optional. Use one shared art-direction brief: product/subject behavior, exact palette, chosen medium, composition, graphic motifs and surface treatment. Avoid unrelated stock imagery. Images intended to be a family should share actual references where useful. The coding agent writes precise briefs and handles HTML/CSS, not the logo's creative drawing or the artwork's replacement with simple code shapes.

6. **Prepare usable exports.** Preserve full composition, silhouette and clear space. The existing `crop-image.py` helper cover-crops and flattens to RGB; use it only when appropriate for that asset. A generated logo can remain PNG/WebP: vector output is not required. Supply a monochrome export and an icon from the same accepted design, either through faithful deterministic export/recolor/crop or a reference-based Gemini edit. Never replace the accepted design with an approximate hand-drawn SVG to satisfy a format preference. Self-contained native SVG derivatives are allowed only if faithful to that design. Every raster must be ≤500 KB; remove oversized raw files. Do not mistake a checkerboard pattern for actual transparency.

7. **Judge artwork, not just file validity.** Inspect every generated image with vision and inspect logos on their actual backgrounds at navigation and icon sizes. Check typography, spelling, kerning, silhouette, contrast, clear space, composition and consistency. Inspect graphics at desktop and mobile display sizes. Compare the result to the requested graphic-design role: photographs plus primitive diagrams cannot pass because there are many assets. Use one targeted correction for a failed asset, then drop it or declare the actual service/quality fallback. No open-ended polish loop.

8. **Record honest provenance in `concept.json`.** Keep `images.rationale`, accepted `items` and `discarded` attempts. For each accepted image record `role`, `file`, `source` (`gemini` or `derived-export` or `native-fallback`), actual prompt, attempt count, placement and verdict. Derived exports name their source file and transformation and have zero generation attempts. Use roles `logo`, `graphic-design`, `infographic` and `photo`/`hero`/`demo`/`testimonial` to make the actual allocation visible. Record logo candidate decisions and rejected calls too. `brand_kit.graphic_plan` must name the two actual graphic files; in normal Gemini mode each must have matching Gemini provenance and be displayed on the landing page. Do not claim a native SVG, a photograph or a basic diagram fulfils the Gemini design requirement.

---

## Step 5 — BUILD LANDING

1. **Invoke the `frontend-design` skill.** This is required — it's the guardrail against generic AI output. Note that its "critique your work with screenshots" advice is deferred to Step 9, under a hard cap — do not render or screenshot anything here.
2. Write a single self-contained HTML file to `site/entries/<slug>/index.html` with:
   - `<head>`: title (`product_name — tagline`), the chosen Google Fonts import (if any) inline. Sharing metadata is finalized in Step 8 by `scripts/build-entry-metadata.py`; keep `concept.json`'s `hero.h1` and `hero.sub` in sync with the hero copy shown on this page.
   - `<style>` block: inline CSS implementing the chosen style + palette + fonts. No external CSS frameworks. No Tailwind CDN. No Bootstrap.
   - `<body>`: hero, features (3), testimonials (3), pricing (3), footer with small "← theworstaistudioever" link to `/`, and a prominent "open the demo →" CTA linking to `./demo.html`.
   - Any JS needed (smooth scroll, etc.) inline in a `<script>` tag.
3. All visible copy passes through `anti-ai-slop` voice rules. No generic AI tells.
4. The page should look like a real, well-funded startup's landing page in the chosen style — not a template.
5. **Apply the accepted Gemini identity throughout.** Place the primary or monochrome logo in the landing navigation and footer. A generated wordmark replaces the typeset product name there; a symbol can sit beside live HTML lettering. Do not add a competing hand-coded mark. Link the brand to this entry's landing page. Use `brand_kit.logo.icon_file` as a local `<link rel="icon">` in the head. Preserve aspect ratio, clear space and minimum size, and choose a variant with visible contrast. On mobile, reduce navigation before shrinking the logo below its minimum size. Give the brand link one accessible product name: use logo alt text when there is no adjacent product-name text, otherwise empty image alt text.
6. Integrate **at least two accepted composed graphic artworks** from `brand_kit.graphic_plan` through local image paths. Give each adequate space to read as a designed composition; do not hide them as tiny thumbnails. They must show graphic design through hierarchy, typography, illustration/collage, layout or information design. Additional photography and basic HTML/SVG diagrams do not satisfy this checkpoint. Keep functional controls and important information available in live HTML, provide an accessible explanation of infographics, and check embedded typography at mobile size. Simplify or regenerate artwork with illegible text. Use the declared native fallback only when the API is actually unavailable.

---

## Step 6 — BUILD DEMO

1. Write `site/entries/<slug>/demo.html` — a single self-contained HTML file containing one interactive screen of the imagined product, populated with fake data.
2. Inherits the palette and typography from step 3, but uses **product-UI layout** (not marketing). Think: a dashboard, a feed, a swipe-stack, a settings page, a config editor — whatever fits the `demo_screen_concept` from step 2.
3. Real interactivity where cheap (vanilla JS, no frameworks): filtering, toggling, modal open/close, drag-reorder, tab switching, fake search. No real API calls — mock everything client-side.
4. Top-left chrome: small back link "← back to the pitch" to `./index.html`.
5. Use `frontend-design` skill while building. Run all visible copy through `anti-ai-slop`.
6. **Carry the same identity into the product.** Show the primary or monochrome logo and product name in the demo chrome, keep the back-to-pitch link, and use the same local icon favicon as the landing page. Reuse the palette, typography, tokens, mark geometry and graphic language, with the density appropriate to product UI. Use accepted demo subject assets via relative paths. Apply a relevant supporting graphic to an empty state, explainer or data summary when useful; keep the main interaction prominent. Slots without API imagery get a native treatment. Never reference a file that does not exist.

---

## Step 7 — GALLERY REBUILD

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

## Step 8 — VALIDATE & RECORD

**This is a checkpoint. Finish all three items below before you do anything optional.** The run has a hard 80-turn cap; work done before this point survives a turn blowout, work done after it does not. On 2026-08-28 the run built a complete, valid entry and then spent its last 35 turns on unrequested polish, hit the cap, and lost the whole day because this step never ran.

1. Run `python3 scripts/build-entry-metadata.py site <slug>`, then `scripts/validate-entry.sh site <slug>` via the Bash tool. If either exits non-zero, abort the run — print the error, do not proceed. The metadata generator updates both landing and demo `<head>` tags deterministically:
   - Title: `product_name — tagline` (demo adds ` — Demo`), reused for the document, Open Graph, and Twitter titles.
   - Description: `hero.h1` followed by `hero.sub`, with markup removed and whitespace collapsed; fall back to `one_liner` only when hero text is absent. Cap at **300 characters including the trailing ellipsis**, truncate at a word boundary when possible, and reuse for standard, Open Graph, and Twitter descriptions.
   - Absolute HTTPS canonical and `og:url` for each page, resolved from `site/CNAME`.
   - A local `social-preview.jpg` (**1200×630, ≤500 KB**) derived from the hero image, or the studio `/logo.png` on the entry's background color when there is no hero. Absolute image URL, dimensions, JPEG MIME type, and alt text for Open Graph and Twitter, with a large-image card. This derivative does not consume an AI image slot.
   - These tags must be present in the static HTML so sharing crawlers can read them without JavaScript. The wrapper regenerates them again before validation and publishing.
2. Append `{date, company, subject, slug}` to `state/history.json`. Read the existing array, append, write back. Maintain JSON validity.
3. Write a run summary to `state/runs/<today>.log`. Include:
   - What was rolled (company, subject, slug).
   - Number of rerolls.
   - Design direction chosen (style, palette, fonts).
   - Brand identity rationale, logo filenames and placements, graphic language, and which supporting graphics shipped (Gemini or native).
   - Image allocation rationale, per-image attempt counts and judge verdicts — or why Gemini was skipped and which native fallbacks shipped.
   - Any warnings or near-misses.
   - Confirmation that validation passed.

---

## Step 9 — VISUAL CHECK (optional, hard-capped)

Everything that matters is already recorded, so this step is pure upside and is allowed to be skipped. It exists because the `frontend-design` skill asks you to critique your own work with screenshots — which is good advice with no natural stopping point, and an unbounded render-critique-fix loop is exactly what blew the turn budget on 2026-08-28.

**Skip this step entirely if any of these are true:**
- A headless browser is not already installed. Check, do not fix: `ls ~/.cache/ms-playwright/ 2>/dev/null`. If the capture command fails for any reason, that is your answer — skip the step. **Never install anything to make this step work.**
- You have already made more than ~55 tool calls this run.
- The entry has no images and a purely typographic design direction (nothing to look at that you did not just write).

**The caps, if you do run it:**
- **At most 2 captures total** — one for `index.html`, one for `demo.html`. Use `scripts/shoot-site.sh "file://$PWD/site/entries/<slug>/index.html" <slug>-landing`.
- **At most 3 corrective edits total**, across both files combined.
- **At most 1 re-capture** after editing, to confirm you did not make it worse.
- Fix only real breakage: overlapping text, an image at the wrong aspect ratio, an element off-canvas, an unreadable contrast pair. Taste-level tweaks are not breakage — leave them.
- Do not write helper scripts to do the capturing. `shoot-site.sh` is the only capture path. If it does not work, skip the step.

That is a ceiling of roughly 8 tool calls. If you are past it, stop and go to Step 10 — a shipped entry with a minor layout wart beats a run that dies at the cap.

**If you edit anything here, re-run `python3 scripts/build-entry-metadata.py site <slug>` and `scripts/validate-entry.sh site <slug>` before Step 10.** Keep hero changes in sync with `concept.json`. The wrapper validates again after you exit, and a polish edit that breaks validation fails the run.

---

## Step 10 — DONE

Print exactly this line to stdout (the wrapper greps for it):

```
RUN_COMPLETE: <slug>
```

Then exit cleanly. **Do NOT run git commands.** The wrapper handles git.

---

## Things to NOT do

- Do not introduce any build step. No npm install. No bundlers.
- Do not install software of any kind — no `playwright install`, no `npm install`, no `pip install`, no `apt`. The run environment is fixed. If a tool is missing, that is a signal to skip the optional step that wanted it, not to go get it.
- Do not write throwaway helper scripts into the repo root. Use a heredoc through `python3 -` when you need a scratch computation, so nothing is left behind to clean up.
- Do not use external CSS frameworks (Tailwind, Bootstrap) in per-entry pages.
- Do not write any file outside the working tree.
- Do not commit, push, or pull.
- Do not skip skill invocations to "save time."
- Do not hotlink images or call the Gemini API except through `scripts/gen-image.sh`. Entry images live inside the entry directory.
- Do not pick a style/palette/fonts tuple that matches any of the last 7 entries.
- Do not earnestly pitch the startup. Commit to the bit.
