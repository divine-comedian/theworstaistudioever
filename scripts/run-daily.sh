#!/usr/bin/env bash
# Daily cron entrypoint for theworstaistudioever.
# - Single-instance lock
# - Pulls latest
# - Runs `claude -p < pipeline.md`
# - Wrapper does git (agent never has push perms)
# - Notifies via ntfy.sh on failure
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

# Load .env if present
if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

DATE_UTC="$(date -u +%F)"
LOG="state/runs/${DATE_UTC}.log"
mkdir -p "$(dirname "$LOG")"

# Single-instance lock — if another invocation is running, exit cleanly
exec 9>".run.lock"
if ! flock -n 9; then
  echo "[$(date -u)] another run in progress — exiting" >> "$LOG"
  exit 0
fi

log() { echo "[$(date -u +%FT%TZ)] $*" | tee -a "$LOG"; }

notify_fail() {
  local msg="$1"
  if [[ -n "${NTFY_TOPIC:-}" ]]; then
    curl -fsSL -X POST \
      -H "Title: theworstaistudioever cron failed" \
      -d "${msg}. See ${LOG}" \
      "https://ntfy.sh/${NTFY_TOPIC}" >/dev/null 2>&1 || true
  fi
}

log "=== daily run start ==="

# Pull latest in case seeds or pipeline changed elsewhere
if ! git pull --rebase --autostash >> "$LOG" 2>&1; then
  log "git pull failed — continuing anyway"
fi

# Snapshot the entries directory before the run, so we know which slug got created
BEFORE_ENTRIES=$(ls site/entries 2>/dev/null | sort || true)

# Run the agent
log "invoking claude -p"
if ! claude -p "$(cat pipeline.md)" \
      --allowed-tools "Read,Write,Edit,Glob,Grep,Bash(jq:*),Bash(node:*),Bash(python3:*),Bash(date:*),Bash(ls:*),Bash(cat:*),Bash(mkdir:*),Bash(./scripts/validate-entry.sh:*),Bash(scripts/validate-entry.sh:*),Skill" \
      --max-turns 80 \
      >> "$LOG" 2>&1; then
  log "RUN FAILED: claude -p exited non-zero"
  notify_fail "claude -p exited non-zero"
  exit 1
fi

# RUN_COMPLETE sentinel is informational only — the authoritative signals are
# "new slug appeared in site/entries/" + "validate-entry.sh passed" (checked below).
if ! grep -q "^RUN_COMPLETE:" "$LOG"; then
  log "WARN: agent did not print RUN_COMPLETE marker — falling through to slug+validate checks"
fi

# Figure out which slug got created
AFTER_ENTRIES=$(ls site/entries 2>/dev/null | sort || true)
NEW_SLUG=$(comm -13 <(echo "$BEFORE_ENTRIES") <(echo "$AFTER_ENTRIES") | head -1)

if [[ -z "$NEW_SLUG" ]]; then
  log "RUN FAILED: no new entry directory created"
  notify_fail "no new entry produced"
  exit 1
fi

log "new entry: $NEW_SLUG"

# Validate the new entry
if ! ./scripts/validate-entry.sh site "$NEW_SLUG" >> "$LOG" 2>&1; then
  log "RUN FAILED: validate-entry rejected $NEW_SLUG"
  notify_fail "validation failed for $NEW_SLUG"
  exit 1
fi

# Commit + push (wrapper, not agent)
TAGLINE=$(jq -r '.tagline' "site/entries/$NEW_SLUG/concept.json")
log "committing: $TAGLINE"

git add . >> "$LOG" 2>&1

# If nothing actually changed in tracked files, log + bail
if git diff --cached --quiet; then
  log "nothing staged — exiting cleanly"
  exit 0
fi

git commit -m "feat: ${TAGLINE}" >> "$LOG" 2>&1

# Push with 3 retries
for i in 1 2 3; do
  if git push >> "$LOG" 2>&1; then
    log "pushed"
    break
  fi
  log "push attempt $i failed; sleeping"
  sleep $((i * 5))
  if [[ "$i" == "3" ]]; then
    log "RUN FAILED: push failed after 3 attempts"
    notify_fail "git push failed after 3 attempts"
    exit 1
  fi
done

log "=== daily run complete: $TAGLINE ==="
