# theworstaistudioever — agent conventions

If you are an agent working in this repo:

- **The daily run prompt is `pipeline.md`.** It is the source of truth for what gets generated each day. Treat changes to it as critical — they ship to production on the next cron tick.
- **Per-entry pages (`site/entries/<slug>/`) are self-contained.** Inline all CSS and JS. No external CSS frameworks (no Tailwind, no Bootstrap, no CDN imports). No build step.
- **The gallery (`site/index.html` + `site/styles.css`) is the stable meta-site shell.** The daily run regenerates `index.html` but never touches `styles.css`. Preserve the root metadata contract in `pipeline.md`, the `/favicon.png` link, the `/logo.png` 50×50 brand lockup, and the responsive carousel nav pattern: fixed arrows with a centered, horizontally scrollable dot rail.
- **`state/history.json` is append-only.** Never rewrite prior entries; only append.
- **You do not push to git.** The wrapper script handles git. Make changes to the working tree only.
- **Voice rule:** every piece of user-facing copy commits to the "worst AI studio ever" bit — dry, faux-corporate, deadpan. Never earnest. Run all copy through the `anti-ai-slop` skill.
- **Design rule:** every entry's design direction (style, palette, fonts) must differ from the last 7 entries. Read the last 7 `concept.json` files before picking direction in step 3 of the pipeline.

The spec lives at `docs/superpowers/specs/2026-05-13-theworstaistudioever-design.md`. Read it before making structural changes.
