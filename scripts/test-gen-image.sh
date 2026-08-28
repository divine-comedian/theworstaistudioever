#!/usr/bin/env bash
# Tests for gen-image.sh — all offline (dry-run, missing key, cap file, args).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
GEN="$SCRIPT_DIR/gen-image.sh"
TMP="$(mktemp -d)"
trap "rm -rf $TMP" EXIT

PASS=0
FAIL=0

ok()  { echo "PASS: $1"; PASS=$((PASS + 1)); }
bad() { echo "FAIL: $1"; FAIL=$((FAIL + 1)); }

# Isolate every test from the real repo .env and state/runs counter.
touch "$TMP/empty.env"
mkdir -p "$TMP/state"
run_gen() {
  env -u GEMINI_API_KEY -u GEMINI_IMAGE_MODEL \
    GEN_IMAGE_ENV_FILE="$TMP/empty.env" GEN_IMAGE_STATE_DIR="$TMP/state" \
    "$@" "$GEN" "${ARGS[@]}"
}

TODAY="$(date -u +%F)"
CAP_FILE="$TMP/state/${TODAY}.imagegen"

# Test 1: --dry-run prints payload with prompt, aspect ratio, and default model
ARGS=("a deadpan corporate headshot of an otter" "16:9" "$TMP/out.png" --dry-run)
if OUT="$(run_gen env 2>/dev/null)" \
   && jq -e '.model == "gemini-3.1-flash-image"' <<<"$OUT" >/dev/null \
   && jq -e '.body.generationConfig.imageConfig.aspectRatio == "16:9"' <<<"$OUT" >/dev/null \
   && jq -e '.body.contents[0].parts[0].text == "a deadpan corporate headshot of an otter"' <<<"$OUT" >/dev/null; then
  ok "dry-run payload has model, aspect, prompt"
else
  bad "dry-run payload has model, aspect, prompt"
fi

# Test 2: GEMINI_IMAGE_MODEL override is reflected in the payload
ARGS=("prompt" "1:1" "$TMP/out.png" --dry-run)
if OUT="$(run_gen env GEMINI_IMAGE_MODEL=test-model-override 2>/dev/null)" \
   && jq -e '.model == "test-model-override"' <<<"$OUT" >/dev/null; then
  ok "GEMINI_IMAGE_MODEL override respected"
else
  bad "GEMINI_IMAGE_MODEL override respected"
fi

# Test 3: dry-run does not create or increment the counter file
if [[ ! -e "$CAP_FILE" ]]; then
  ok "dry-run does not touch counter file"
else
  bad "dry-run does not touch counter file"
fi

# Test 4: missing GEMINI_API_KEY (non-dry-run) exits non-zero with clear message
ARGS=("prompt" "1:1" "$TMP/out.png")
if ERR="$(run_gen env 2>&1)"; then
  bad "missing key exits non-zero"
else
  if grep -q "GEMINI_API_KEY" <<<"$ERR"; then
    ok "missing key exits non-zero"
  else
    bad "missing key exits non-zero (no GEMINI_API_KEY in message: $ERR)"
  fi
fi

# Test 5: missing key path did not create the counter file
if [[ ! -e "$CAP_FILE" ]]; then
  ok "missing key does not touch counter file"
else
  bad "missing key does not touch counter file"
fi

# Test 6: counter at cap refuses with IMAGEGEN_CAP_REACHED, no increment
echo 10 > "$CAP_FILE"
ARGS=("prompt" "1:1" "$TMP/out.png")
if ERR="$(run_gen env GEMINI_API_KEY=dummy 2>&1)"; then
  bad "cap reached refuses"
else
  if grep -q "IMAGEGEN_CAP_REACHED" <<<"$ERR" && [[ "$(cat "$CAP_FILE")" == "10" ]]; then
    ok "cap reached refuses without incrementing"
  else
    bad "cap reached refuses without incrementing (err: $ERR, count: $(cat "$CAP_FILE"))"
  fi
fi
rm -f "$CAP_FILE"

# Test 7: unsupported aspect ratio exits non-zero
ARGS=("prompt" "7:3" "$TMP/out.png" --dry-run)
if run_gen env >/dev/null 2>&1; then
  bad "invalid aspect ratio rejected"
else
  ok "invalid aspect ratio rejected"
fi

# Test 8: wrong number of args exits non-zero with usage
ARGS=("only-a-prompt")
if ERR="$(run_gen env 2>&1)"; then
  bad "bad arg count rejected"
else
  if grep -qi "usage" <<<"$ERR"; then
    ok "bad arg count rejected"
  else
    bad "bad arg count rejected (no usage in: $ERR)"
  fi
fi

# --- HTTP retry / counter-accounting tests ------------------------------------
# Regression cover for 2026-08-28: Gemini returned ten consecutive 503s, and the
# counter (then incremented before the call) charged the daily budget for calls
# that produced no image. A `curl` shim on PATH replays a scripted sequence of
# HTTP codes so these run offline.
SHIM="$TMP/shim"
mkdir -p "$SHIM"
cat > "$SHIM/curl" <<'SHIMEOF'
#!/usr/bin/env bash
# Replays codes from $SHIM_CODES (space separated), one per invocation.
# Honours `-o <file>` and prints the code, like `curl -o F -w '%{http_code}'`.
OUT=""
prev=""
for a in "$@"; do
  [[ "$prev" == "-o" ]] && OUT="$a"
  prev="$a"
done
N="$(cat "$SHIM_STATE" 2>/dev/null || echo 0)"
N=$((N + 1))
echo "$N" > "$SHIM_STATE"
read -r -a CODES <<< "$SHIM_CODES"
IDX=$((N - 1))
CODE="${CODES[$IDX]:-${CODES[${#CODES[@]}-1]}}"
if [[ -n "$OUT" ]]; then
  if [[ "$CODE" == "200" ]]; then
    printf '{"candidates":[{"content":{"parts":[{"inlineData":{"data":"%s"}}]}}]}' \
      "$(printf 'PNGDATA' | base64 -w0)" > "$OUT"
  else
    printf '{"error":{"code":%s,"message":"shim"}}' "$CODE" > "$OUT"
  fi
fi
printf '%s' "$CODE"
SHIMEOF
chmod +x "$SHIM/curl"

# Test 9: persistent 503 exhausts 3 attempts, fails, and does NOT charge the cap
rm -f "$CAP_FILE"
echo 0 > "$TMP/shim.state"
ARGS=("prompt" "1:1" "$TMP/out9.png")
if ERR="$(run_gen env PATH="$SHIM:$PATH" SHIM_CODES="503 503 503" \
          SHIM_STATE="$TMP/shim.state" GEN_IMAGE_RETRY_BASE_SLEEP=0 \
          GEMINI_API_KEY=dummy 2>&1)"; then
  bad "persistent 503 exits non-zero"
else
  ATTEMPTS="$(cat "$TMP/shim.state")"
  if [[ "$ATTEMPTS" == "3" ]] && [[ ! -e "$CAP_FILE" ]]; then
    ok "persistent 503 retries 3x and does not charge the daily cap"
  else
    bad "persistent 503 (attempts: $ATTEMPTS, want 3; cap file: $(cat "$CAP_FILE" 2>/dev/null || echo absent), want absent)"
  fi
fi

# Test 10: 503 then 200 succeeds, and charges the cap exactly once
rm -f "$CAP_FILE"
echo 0 > "$TMP/shim.state"
ARGS=("prompt" "1:1" "$TMP/out10.png")
if ERR="$(run_gen env PATH="$SHIM:$PATH" SHIM_CODES="503 200" \
          SHIM_STATE="$TMP/shim.state" GEN_IMAGE_RETRY_BASE_SLEEP=0 \
          GEMINI_API_KEY=dummy 2>&1)"; then
  if [[ "$(cat "$CAP_FILE" 2>/dev/null)" == "1" ]] && [[ -s "$TMP/out10.png" ]]; then
    ok "503 then 200 succeeds and charges the cap once"
  else
    bad "503 then 200 (cap: $(cat "$CAP_FILE" 2>/dev/null || echo absent), want 1; out: $(wc -c < "$TMP/out10.png" 2>/dev/null || echo 0) bytes)"
  fi
else
  bad "503 then 200 succeeds ($ERR)"
fi

# Test 11: a non-retryable 400 fails on the first attempt, no cap charge
rm -f "$CAP_FILE"
echo 0 > "$TMP/shim.state"
ARGS=("prompt" "1:1" "$TMP/out11.png")
if ERR="$(run_gen env PATH="$SHIM:$PATH" SHIM_CODES="400" \
          SHIM_STATE="$TMP/shim.state" GEN_IMAGE_RETRY_BASE_SLEEP=0 \
          GEMINI_API_KEY=dummy 2>&1)"; then
  bad "400 exits non-zero without retrying"
else
  if [[ "$(cat "$TMP/shim.state")" == "1" ]] && [[ ! -e "$CAP_FILE" ]]; then
    ok "400 fails on first attempt without charging the cap"
  else
    bad "400 (attempts: $(cat "$TMP/shim.state"), want 1; cap: $(cat "$CAP_FILE" 2>/dev/null || echo absent))"
  fi
fi
rm -f "$CAP_FILE"

echo ""
echo "Results: $PASS passed, $FAIL failed"
[[ $FAIL -eq 0 ]]
