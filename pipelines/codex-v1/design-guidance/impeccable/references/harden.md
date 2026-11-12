> Adapted from Impeccable's harden.md at commit b4bff16. Modified for this pipeline as text-only guidance; see SOURCE.json and LICENSE.

# Harden the demonstrated workflow

Identify states and transitions in the advertised demo: initial state, selection, action, completion, reset, cancellation and another attempt. Keep the result, enabled controls, counters and selected items consistent at every transition.

Test what happens after success, not only how success is reached. Returning to a form must preserve a valid selection or clearly request another one. A completed reservation or consumed resource must remain accounted for. Repeated actions should either make another valid change or explain why they are unavailable; avoid silent no-ops and accidental duplicate results.

Exercise the limits that this demo actually exposes: minimum and maximum values, no matches, no available choices, long labels, cleared input, multiple selections, plan changes and reset. Match prices, units, allowances and outcomes to the landing copy. A plan preview must say what it demonstrates and must not imply a purchase or entitlement that was not provided.

Keep errors near the relevant input, preserve useful user input, and state how to recover. Use plain action labels and truthful status messages. Retain the product's humor in its situations and consequences while making recovery instructions unambiguous.

Allow labels and descriptions to wrap; check text growth and relevant character sets when the supplied content calls for them. Keep dates, numbers and quantities understandable. Do not expand a local demo into an internationalization system or add server-side features that are outside its brief.

For custom pointer interactions, clear transient state on cancellation, lost capture or focus changes so the next action still works. Report whether input behavior was actually exercised or only inspected in source. Keyboard controls and dynamic feedback should remain understandable.

Use existing tools and the host's interaction plan to verify changed state. A success toast alone does not prove the underlying selection, count or availability changed. If the host test is wrong, describe the specific mismatch; do not break the product to satisfy it.

Repairs stay within the host's finding targets, file allowlist, identity constraints and remaining allowance. This reference does not permit regenerating artwork, modifying pipeline scripts, adding dependencies, starting another review loop or publishing.
