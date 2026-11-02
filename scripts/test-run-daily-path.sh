#!/usr/bin/env bash
# Verifies run-daily.sh resolves its own tool dependencies under cron's bare
# PATH, for the active Codex generator and the archived Claude fallback.
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
RUNNER="$REPO_ROOT/scripts/run-daily.sh"
CRON_PATH="/usr/bin:/bin"
pass=0; fail=0
ok()   { echo "  ok — $1"; pass=$((pass+1)); }
bad()  { echo "  FAIL — $1"; fail=$((fail+1)); }

echo "test-run-daily-path"

# 1. Baseline: prove the cron environment really is missing codex, so this
#    test would have caught the outage.
if env -i PATH="$CRON_PATH" HOME="$HOME" sh -c 'command -v codex' >/dev/null 2>&1; then
  ok "baseline: codex already on bare cron PATH (nothing to harden)"
else
  ok "baseline: codex absent from bare cron PATH (the outage condition)"
fi

# 2. The runner must succeed at preflight under cron's exact environment.
out="$(env -i PATH="$CRON_PATH" HOME="$HOME" "$RUNNER" --preflight 2>&1)"
rc=$?
if [[ $rc -eq 0 ]]; then
  ok "run-daily.sh --preflight exits 0 under cron PATH"
else
  bad "run-daily.sh --preflight exited $rc under cron PATH"
  echo "$out" | sed 's/^/      /'
fi

# 3. Preflight must actually report a resolved codex binary.
if grep -q 'codex -> /' <<<"$out"; then
  ok "preflight resolved the codex binary"
else
  bad "preflight did not report a resolved codex path"
  echo "$out" | sed 's/^/      /'
fi

fallback="$(env -i PATH="$CRON_PATH" HOME="$HOME" PIPELINE_ENGINE=claude "$RUNNER" --preflight 2>&1)"
if [[ $? -eq 0 ]] && grep -q 'claude preflight: archived prompt available' <<<"$fallback"; then
  ok "Claude rollback preflight succeeds under cron PATH"
else
  bad "Claude rollback preflight failed"
  echo "$fallback"
fi

echo "  $pass passed, $fail failed"
[[ $fail -eq 0 ]]
