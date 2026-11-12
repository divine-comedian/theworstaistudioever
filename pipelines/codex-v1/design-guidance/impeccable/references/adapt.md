> Adapted from Impeccable's adapt.md at commit b4bff16. Modified for this pipeline as text-only guidance; see SOURCE.json and LICENSE.

# Adapt layout and interaction

Adapt the experience to the available space and input method, rather than shrinking a desktop picture. Preserve the source service's information architecture, primary actions, essential content and audience identity across sizes.

Plan for the actual content at 1440px, 390px and 320px. Choose breakpoints where content stops fitting, not only at conventional device widths. Reflow sidebars, legends, comparisons and control groups when they need more room.

Grid and flex children have intrinsic minimum sizes. Use shrinkable tracks such as minmax(0, 1fr), min-width: 0 where appropriate, and wrapping or stacking for label groups. Check long labels and completed states, not just empty controls. Let containers grow with readable text. Page-level overflow hiding, clipped labels and squeezed fonts do not fix a width defect.

Keep the main workflow available on mobile. Collapse secondary material only when it remains discoverable with a clear control. Reorder for task priority, without changing what a selection or action means. Do not add drawers, bottom navigation, sticky elements or gestures merely because the screen is narrow.

Keep tap targets separated, keyboard focus usable, and essential feedback visible. Provide an alternative when hover, drag or precise pointing is the only way to act. For a custom gesture, consider pointer cancellation and page scrolling; do not claim that these work from a screenshot alone.

Artwork may need a different scale or placement while retaining the accepted composition and essential content. Keep explanatory captions attached and readable. A diagram or game arena can use its own deliberate viewport, but its labels and controls still need an intelligible alternative when too small.

Use the host's batched browser evidence and repair allowance. Check intermediate widths or expanded states when an observed defect calls for it. Report emulated widths and executed inputs accurately; do not require new devices, browser installations or an additional approval workflow.
