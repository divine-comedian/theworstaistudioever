> Adapted from Impeccable's audit.md at commit b4bff16. Modified for this pipeline as text-only guidance; see SOURCE.json and LICENSE.

# Audit implementation evidence

Review the actual interface and existing technical evidence. Keep verifiable implementation findings distinct from visual judgment. A static source check, a rendered screenshot and an executed interaction establish different things.

## Accessibility and readability

Prefer semantic links, buttons, labels and headings. Check meaningful accessible names, visible focus, logical keyboard order and understandable selection or expanded states. Important information needs a live-text equivalent; color alone should not distinguish availability, errors or progress.

Aim for body-text contrast of at least 4.5:1 and large-text contrast of 3:1. Check real foreground/background combinations, including muted text, focus and disabled treatments. Comfortable touch controls are generally around 44px with adequate spacing; do not apply that heuristic as a blanket failure to ordinary inline links. Do not claim full accessibility conformance from these checks alone.

## Layout, state and assets

Use all supplied captures at 1440px, 390px and 320px. Inspect the proposition, primary control, captions, pricing and demo controls at each size. Check expanded or completed states as well as the initial screen.

Read global browser failures as well as individual viewport findings. A missing gallery link or failed resource still matters when page rows look clean. Distinguish a failed checker expectation from a product defect; report mistaken tests to the host instead of changing correct behavior.

Check asset aspect ratios, placement, legibility and consistency with live values. A deferred image inside a closed panel is not broken merely because it has not loaded yet; use the host's explicit image-loading checks and actual resource failures. Preserve the pipeline's local-asset and size limits.

## Scope and performance

Look for unnecessary layout work, expensive continuous effects, unstable image dimensions and misleading loading states. Keep tokens consistent within the approved theme; do not require a dark theme, framework, new dependency or backend that the product does not have.

A viewport emulation proves layout at that width, not a physical phone or a successful touch gesture. Identify what the host actually exercised and what remains source-based or untested. Feed material failures into the existing QA checks and finding schema. Do not run an upstream detector or install tooling.
