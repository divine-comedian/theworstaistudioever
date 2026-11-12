# theworstaistudioever — agent conventions

If you are an agent working in this repo:

- **The daily run prompt is `pipeline.md`.** It is the source of truth for what gets generated each day. Treat changes to it as critical — they ship to production on the next cron tick.
- **Per-entry pages (`site/entries/<slug>/`) are self-contained.** Inline all CSS and JS. No external CSS frameworks (no Tailwind, no Bootstrap, no CDN imports). No build step. Entry images are local files inside the entry directory — never hotlinked.
- **The gallery (`site/index.html` + `site/styles.css`) is the stable meta-site shell.** The daily run regenerates `index.html` but never touches `styles.css`. Preserve the root metadata contract in `pipeline.md`, the `/favicon.png` link, the `/logo.png` 50×50 brand lockup, and the responsive carousel nav pattern: fixed arrows with a centered, horizontally scrollable dot rail.
- **`state/history.json` is append-only.** Never rewrite prior entries; only append.
- **You do not push to git.** The wrapper script handles git. Make changes to the working tree only.
- **Voice rule:** build straight-faced humor from recognizable audience behavior exaggerated through the source product's mechanics. Make the product and its absurd consequences understandable on first reading. Run all copy through the `anti-ai-slop` skill.
- **Audience rule:** the source company supplies the service structure and demo workflow; the audience supplies the visual identity. Ground type, color, imagery and composition in concrete audience references before asset generation. Humor must work for a casual outsider and contain a comic turn beyond offering a plausible niche service.
- **Supporting design guidance:** the Codex host inlines a pinned text-only Impeccable adaptation from `pipelines/codex-v1/design-guidance/impeccable/`. It supports the existing design and QA steps; user intent, audience references, satire, the quality floor and repair limits take precedence. No upstream tooling or additional workflow is installed.
- **Quality rule:** every daily entry must meet or exceed the user-approved repaired Again entry of 2026-11-11. The pinned rubric and screenshots are in `pipelines/codex-v1/quality-floor.json`. Compare clarity, specific humor, useful imagery, visual finish and mobile usability while creating an original identity. A below-standard draft must be repaired or withheld from publication.
- **Design rule:** every entry's design direction (style, palette, fonts) must differ from the last 7 entries. Use the host's recent-entry digest when supplied; otherwise read the last 7 `concept.json` files before picking direction in step 3 of the pipeline. Compare comic mechanisms and composition as well.

The spec lives at `docs/superpowers/specs/2026-05-13-theworstaistudioever-design.md`. Read it before making structural changes.
