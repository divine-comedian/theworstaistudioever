# Codex quality contract, revision 2

Read this before generating concept copy or selecting a visual direction. It
supplements pipeline.md. The trial constraints and the user's requirements take
precedence over generic skill defaults. Produce a new implementation and new
copy; do not imitate another generated entry.

## Separate the two surfaces

The company in the tagline supplies a product model, not just a word in a joke.
Identify its characteristic information architecture and user actions. Preserve
those recognizable patterns in the demo while adapting the data to the subject.
An attractive generic dashboard is a failure when the source product has a
distinctive workflow. A workspace, marketplace, messenger, and dating app should
have different structures before any colors are applied.

The landing page sells that product. It should have a clear proposition, a
convincing product visual, useful feature demonstrations, testimonials, pricing,
and a clear route into the demo. Compose a coherent SaaS page, with one restrained
subject-specific visual motif. Do not turn it into an event invitation, poster,
editorial spread, or a collection of equally weighted decorated boxes unless
that is explicitly the requested product.

Use the frontend-skill for composition and restraint, frontend-design for
subject-specific choices, and ui-ux-pro-max for typography, palettes, and
interaction guidance. Resolve their defaults against this brief: a product-led
SaaS page can use a real HTML product preview as its visual anchor. Existing
testimonial portraits belong with the testimonials. Do not add a photographic
hero, full-screen poster, large brand masthead, or decorative motion merely to
satisfy a generic skill example. Calm typography and whitespace are legitimate
when the source product calls for them. Two typefaces maximum; the demo may use
a functional sans-serif even if the landing uses a display face.

## Make the satire observable

The humor comes from a real habit or social friction of the subject, treated as
a problem serious software would proudly administer. Choose three different
observations. Each feature, testimonial, pricing limit, empty state, and mock
record should develop one of them with concrete detail.

Write the copy before the HTML, then edit it once. Draft three headline options
and select the clearest one that contains an actual comic premise. A polished
but literal benefit statement does not meet the voice requirement. For each
feature, the software should solve a recognizably wrong problem, rather than
merely give a plausible feature a silly name.

Use specific circumstances, small numbers, occupations, habits, objects, and
consequences that belong to this audience. Testimonials should sound like
someone recounting what happened after using the product, with a detail that
could not be swapped into another concept. Pricing should escalate the same
product delusion through specific entitlements and constraints. Random large
prices and generic enterprise terminology are not sufficient jokes.

Avoid recycling a single observation across all three features. Avoid making
every joke about permission levels, legal blame, stakeholders, procurement,
audit trails, or AI itself. Those can support a joke when earned, but cannot
replace knowledge of the subject. Give the audience recognizable behavior
rather than a blanket caricature. Keep useful UI labels plain and put most
satire in the data, product rules, secondary text, and consequences of actions.

Every advertised behavior represented in the demo must agree with its data
model. If the product promises one record per item, creating that item again
must update the existing record rather than silently create a duplicate. Apply
the same rule to creation, template imports, counters, filters, and plan limits.
Enforce limits on the unit that the pricing page actually sells.

Preserve the deadpan fiction throughout the product. Do not add a footer that
announces this is fictional, a demo disclaimer, jokes about this coding task,
implementation notes, or copy that explains why a joke is funny. Required studio
links remain. Never copy a headline, testimonial, or punchline from the baseline
or the first Codex trial.

## Plan before building, edit before declaring completion

Write quality-plan.json with these fields before generating HTML:

- source_product_patterns: at least four recognizable layout/interaction patterns.
- primary_workflow: a short description of what the user actually does.
- landing_direction: palette, type roles, section hierarchy, and product visual.
- demo_direction: density, navigation, typography, record editing, and mobile plan.
- satire_observations: three distinct audience behaviors driving the copy.
- headline_candidates: three independently written options; selected_headline.

Keep this artifact concise. It is a set of design decisions, not a reasoning
transcript. Record the selected direction in concept.json as usual.

Before completion, perform one bounded editing pass. Check whether the first
screen resembles the source product, whether all prominent controls work, and
whether the copy has funny details rather than only a satirical premise. Cut
repeated gags, generic marketing filler, weak testimonials, decorative chrome,
unnecessary banners, and any mismatch between the concept and visible content.

Write quality-review.json with these fields:

- source_fidelity: visible features and behaviors supporting recognizability.
- landing_composition: hierarchy and restraint decisions actually implemented.
- satire: strongest surviving lines and the repeated or weak material removed.
- mobile_plan: how navigation and record actions fit a narrow screen.
- limits: checks deferred to the host; do not claim browser or screenshot checks.

The host will independently inspect screenshots and exercise interactions after
the run. Self-review is useful evidence of work performed, not proof of quality.
If the host supplies host-feedback.txt, make one bounded repair pass against
the reported defects. Preserve unaffected design, copy, assets, and history;
record the repair in quality-review.json, rerun validation, and report only
checks actually performed. Never replace a reported failure with an unsupported
claim that it works.
Run metadata generation and validation again after editing, then emit the usual
RUN_COMPLETE marker. Keep all comparison artifacts outside the public product.
