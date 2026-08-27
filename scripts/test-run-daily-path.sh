#!/usr/bin/env bash
# Verifies run-daily.sh resolves its own tool dependencies under cron's bare
# PATH. Regression test for the 2026-08-09..08-27 outage: the crontab's only
# PATH= line sits below this job, so cron handed the runner /usr/bin:/bin and
# `claude` (installed to ~/.local/bin) was not found for 19 nights.
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
RUNNER="$REPO_ROOT/scripts/run-daily.sh"
CRON_PATH="/usr/bin:/bin"
pass=0; fail=0
ok()   { echo "  ok — $1"; pass=$((pass+1)); }
bad()  { echo "  FAIL — $1"; fail=$((fail+1)); }

echo "test-run-daily-path"

# 1. Baseline: prove the cron environment really is missing claude, so this
#    test would have caught the outage.
if env -i PATH="$CRON_PATH" HOME="$HOME" sh -c 'command -v claude' >/dev/null 2>&1; then
  ok "baseline: claude already on bare cron PATH (nothing to harden)"
else
  ok "baseline: claude absent from bare cron PATH (the outage condition)"
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

# 3. Preflight must actually report a resolved claude binary.
if grep -q 'claude -> /' <<<"$out"; then
  ok "preflight resolved the claude binary"
else
  bad "preflight did not report a resolved claude path"
  echo "$out" | sed 's/^/      /'
fi

echo "  $pass passed, $fail failed"
[[ $fail -eq 0 ]]
