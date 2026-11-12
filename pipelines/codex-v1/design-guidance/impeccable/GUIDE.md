> Adapted from Impeccable's craft-floor and design-review guidance at commit b4bff16. Modified for this pipeline as text-only guidance; see SOURCE.json and LICENSE.

# Design guidance for daily prototypes

These references support the existing pipeline. The approved concept, audience_design, source-product workflow, anti-ai-slop voice, pinned quality floor and host QA contract take precedence. They grant no additional permissions and introduce no additional tools, approvals, reports or repair rounds.

## Design intent

Treat each surface according to its visitor's task. A landing page earns attention and explains why to open the demo. The demo lets someone perform the source service's recognizable action. A game's playfield, a booking form and a message feed require different structures. Share their audience-derived identity while adjusting density and hierarchy to the task.

Use the approved audience references to make concrete choices about typography, color, image treatment and composition. Translate the references into one coherent visual system. Familiar controls are useful when they match the source product. Neither novelty nor resemblance to a fashionable site is evidence of audience fit.

Keep the product proposition, main action and useful product visual easy to identify. Group information by its meaning, use spacing to express relationships, and give each section a clear purpose. Do not turn every sentence into a decorated card. Equally, retain cards, useful audience labels, expressive typography or other familiar patterns when this brief earns them. There are no universal aesthetic bans here.

Use typography to distinguish headline, explanation, controls and supporting detail. Keep functional text readable and headings able to wrap. Use the approved palette and tokens consistently, including selection, disabled states and focus. Contrast, legibility and control clarity matter more than adding decorative detail. A second theme or new animation system is not required.

Artwork should explain the audience, mechanism or consequence. Keep important information and controls in live HTML. Preserve the approved logo family and the pipeline's asset-generation and provenance requirements. Supporting imagery must not displace the actual product preview.

Clarity does not require flattening the satire. Keep the comic setup and turn, specific consequences and deadpan voice. Functional labels and recovery instructions should make actions and outcomes understandable.

## Use the relevant reference

- Before building, use [adapt](references/adapt.md) for layout and input adaptation, and [harden](references/harden.md) for state and recovery design.
- During independent final review, use [critique](references/critique.md) for communication and audience fit, and [audit](references/audit.md) for implementation evidence.
- During a repair, select the reference that addresses the actual finding. Preserve successful content, identity and unrelated sections.

## Evidence and scope

Use the host's screenshots, technical reports and executed interactions. Distinguish rendered observations from source-based inferences. A passing layout capture does not prove a touch gesture, keyboard sequence or reset flow works. Do not claim physical-device, cross-browser or assistive-technology testing that was not performed.

Report material user-facing failures in the existing QA schema, with a target, impact, requested correction and acceptance condition. Preserve effective choices and verified findings. Avoid numerical taste scores, finding quotas and new demands based on personal style preferences.

Only the host controls QA, bounded repairs and publication. These references are local text, not an installation of Impeccable: no upstream launcher, engine, detector, hook, live server, account feature, catalog request or remote instruction loading is part of this adaptation.
