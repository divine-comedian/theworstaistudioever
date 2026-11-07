You are running the daily startup pipeline with Codex. Execute pipeline.md in
the current workspace. Read CLAUDE.md for the shared repository conventions.

Use the same three skills as the preferred first Codex comparison. Before the
corresponding pipeline steps, read and apply these local skill instructions:

- pipelines/codex-v1/skills/anti-ai-slop/SKILL.md
- pipelines/codex-v1/skills/ui-ux-pro-max/SKILL.md
- pipelines/codex-v1/skills/frontend-design/SKILL.md

Reading and following these files satisfies the prompt's Skill invocations.
Use their bundled resources at those paths. Use Codex's local shell, file, and
image-viewing tools where pipeline.md refers to Bash, Read, Write, or Edit.
The pipeline's explicit requirements take precedence over generic skill defaults.

Keep the original freedom to select style, palette, fonts, and satire. The
chosen setup uses pipeline.md and these three skills. Other experimental prompt
files and comparison feedback are separate experiments, not daily instructions.

This is a real daily run: roll today's novel pair, create a new concept and both
pages, generate images through scripts/gen-image.sh when available, rebuild the
gallery, validate, and append to history. Build the required per-entry brand kit,
Gemini-designed logo family and composed graphic artwork described in Steps 3–6.
The coding agent briefs and integrates; it must not substitute a hand-coded logo
or extra photographs/basic diagrams for Gemini's actual graphic-design work.
Use the approved logo as an image reference for the related artwork. Gemini allows up to
12 distinct assets per entry and defaults to 24 successful calls per UTC day;
the script enforces any GEMINI_IMAGE_DAILY_LIMIT override. If Gemini is
unavailable, complete the logo and graphics with native SVG/HTML/CSS.
Existing entries and history records must be preserved.

The wrapper supplies a time limit instead of Claude's 80-turn limit. Complete
the validation-and-record checkpoint before optional screenshot polish. Never
install software. If an optional capture tool is unavailable, skip that step.

Work only in this workspace. Do not run git commands, alter the pipeline or
wrapper, delegate, use connected apps, send notifications, or deploy anything.
The wrapper owns publishing and notifications. Never inspect credentials or
print .env contents; the existing image script loads its key itself.

After generation, the host runs one separate QA gate with at most two targeted
repair attempts and fresh reviews. Do not run that loop yourself or edit its
reports. The host owns the final publication decision.

Finish with RUN_COMPLETE: <slug> only after metadata generation, validation,
history append, and the run summary are complete. If required work fails, report
the failure without claiming completion.
