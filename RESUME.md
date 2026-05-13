# Resume guide

Hand this to a fresh Claude Code session you start inside this repo:

```
cd /home/mitch/github/theworstaistudioever
claude
```

Then paste the prompt at the bottom of this file. The session will pick up the implementation plan and continue from where the last session left off.

## Where we are

Task 1 of 11 is complete and committed (`4bba0a6 feat: initialize repo skeleton`). The full implementation plan with all 11 tasks lives at:

- **Spec:** `docs/superpowers/specs/2026-05-13-theworstaistudioever-design.md`
- **Plan:** `docs/superpowers/plans/2026-05-13-theworstaistudioever.md`
- **Repo conventions:** `CLAUDE.md`

`git log --oneline` reflects current task completion — one commit per task is the working convention.

## Remaining tasks

| # | Task | Driver |
|---|---|---|
| ~~1~~ | ~~Initialize repo + skeleton~~ | ~~Done~~ |
| 2 | Generate seed data (companies + subjects JSON, plus 5×5 test seeds) | Agent (you) |
| 3 | Build validation script (`scripts/validate-entry.sh`) with TDD | Agent (you) |
| 4 | Build gallery shell (`site/styles.css`, empty-state `index.html`, `404.html`) | Agent (you) |
| 5 | Write `pipeline.md` (the daily run prompt — heart of the system) | Agent (you) |
| 6 | Build `scripts/run-daily.sh` cron wrapper | Agent (you) |
| 7 | Build `scripts/test-pipeline.sh` dry-run harness | Agent (you) |
| 8 | First dry run + iterate on `pipeline.md` | User + agent |
| 9 | Create GitHub repo, enable Pages, configure DNS for theworstaistudioever.com | User |
| 10 | Configure `.env`, first real run, install crontab | User |
| 11 | First-week monitoring; tune prompt as patterns emerge | User |

## Permissions

`.claude/settings.json` already allowlists everything the plan needs (git, gh, jq, shellcheck, python3, claude CLI nested invocation, scripts/ execution, etc.) and denies the destructive footguns (force-push, rm -rf /, crontab -r). The next session should rarely see a permission prompt.

## Prompt for the fresh session

Paste this when the new session starts:

```
We're mid-implementation on a plan stored at docs/superpowers/plans/2026-05-13-theworstaistudioever.md.
Task 1 is done. Continue execution with the superpowers:subagent-driven-development skill:
dispatch a fresh subagent per task, run spec-compliance review then code-quality review per task,
mark each task complete in TodoWrite as you go.

Drive Tasks 2 through 7 continuously without checking in. When Task 7 is committed, stop and
surface for Task 8 (first dry run — I need to eyeball output with you).

Read CLAUDE.md before dispatching anything.
```
