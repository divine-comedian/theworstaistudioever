#!/usr/bin/env bash
# Daily cron entrypoint for theworstaistudioever.
# - Single-instance lock
# - Pulls latest
# - Runs `claude -p < pipeline.md`
# - Wrapper does git (agent never has push perms)
# - Notifies success/failure to Telegram (reuses aurevon-outreach bot creds)
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

# Telegram notifications reuse the aurevon-outreach bot token + chat id.
# Creds are read at runtime from that project's .env (never committed in this
# public repo); this repo's own .env may override them if set.
AUREVON_ENV="${AUREVON_ENV:-$HOME/github/aurevon-outreach/.env}"
_read_env_var() { # _read_env_var KEY FILE -> value with surrounding quotes stripped
  local key="$1" file="$2" val
  [[ -f "$file" ]] || return 0
  val="$(grep -E "^${key}=" "$file" 2>/dev/null | head -1 | cut -d= -f2- || true)"
  val="${val%\"}"; val="${val#\"}"; val="${val%\'}"; val="${val#\'}"
  printf '%s' "$val"
}
TELEGRAM_BOT_TOKEN="${TELEGRAM_BOT_TOKEN:-$(_read_env_var TELEGRAM_BOT_TOKEN "$AUREVON_ENV")}"
TELEGRAM_USER_ID="${TELEGRAM_USER_ID:-$(_read_env_var TELEGRAM_USER_ID "$AUREVON_ENV")}"

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

_html_escape() { local s="$1"; s="${s//&/&amp;}"; s="${s//</&lt;}"; s="${s//>/&gt;}"; printf '%s' "$s"; }

tg_send() { # tg_send <html-message>
  if [[ -z "${TELEGRAM_BOT_TOKEN:-}" || -z "${TELEGRAM_USER_ID:-}" ]]; then
    log "telegram creds missing — skipping notification"
    return 0
  fi
  curl -fsSL -X POST \
    "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
    -H "Content-Type: application/json" \
    --data "$(jq -n --arg chat "$TELEGRAM_USER_ID" --arg text "$1" \
              '{chat_id:$chat, text:$text, parse_mode:"HTML"}')" \
    >/dev/null 2>&1 || log "telegram send failed"
}

notify_fail() {
  tg_send "❌ <b>theworstaistudioever</b> daily run failed
$(_html_escape "$1")
See ${LOG}"
}

notify_success() { # notify_success <tagline> <product_name> <url>
  tg_send "✅ <b>theworstaistudioever</b> shipped a new startup
<b>$(_html_escape "$1")</b> — $(_html_escape "$2")
🔗 <a href=\"$3\">$3</a>"
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

PRODUCT_NAME=$(jq -r '.product_name // .company // .tagline' "site/entries/$NEW_SLUG/concept.json")
DOMAIN=$(cat site/CNAME 2>/dev/null || echo "theworstaistudioever.com")
PAGE_URL="https://${DOMAIN}/entries/${NEW_SLUG}/"

notify_success "$TAGLINE" "$PRODUCT_NAME" "$PAGE_URL"
log "=== daily run complete: $TAGLINE → $PAGE_URL ==="
