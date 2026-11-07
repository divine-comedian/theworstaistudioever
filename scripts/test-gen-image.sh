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
  env -u GEMINI_API_KEY -u GEMINI_IMAGE_MODEL -u GEMINI_IMAGE_DAILY_LIMIT \
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
echo 24 > "$CAP_FILE"
ARGS=("prompt" "1:1" "$TMP/out.png")
if ERR="$(run_gen env GEMINI_API_KEY=dummy 2>&1)"; then
  bad "cap reached refuses"
else
  if grep -q "IMAGEGEN_CAP_REACHED" <<<"$ERR" && [[ "$(cat "$CAP_FILE")" == "24" ]]; then
    ok "cap reached refuses without incrementing"
  else
    bad "cap reached refuses without incrementing (err: $ERR, count: $(cat "$CAP_FILE"))"
  fi
fi
rm -f "$CAP_FILE"

# A configured budget is enforced independently of the default.
echo 3 > "$CAP_FILE"
if ERR="$(run_gen env GEMINI_API_KEY=dummy GEMINI_IMAGE_DAILY_LIMIT=3 2>&1)"; then
  bad "custom daily cap refuses"
elif [[ "$ERR" == *"IMAGEGEN_CAP_REACHED (3/3"* && "$(cat "$CAP_FILE")" == "3" ]]; then
  ok "custom daily cap refuses without incrementing"
else
  bad "custom daily cap diagnostic or count incorrect ($ERR)"
fi
rm -f "$CAP_FILE"

for LIMIT in 0 -1 2.5 unlimited '' 024; do
  if ERR="$(run_gen env GEMINI_API_KEY=dummy GEMINI_IMAGE_DAILY_LIMIT="$LIMIT" 2>&1)"; then
    bad "invalid daily limit '$LIMIT' accepted"
  elif [[ "$ERR" == *"GEMINI_IMAGE_DAILY_LIMIT must be a positive integer"* && ! -e "$CAP_FILE" ]]; then
    ok "invalid daily limit '$LIMIT' rejected before HTTP or accounting"
  else
    bad "invalid daily limit '$LIMIT' diagnostic or accounting incorrect ($ERR)"
  fi
done

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
REQUEST=""
for a in "$@"; do
  [[ "$prev" == "-o" ]] && OUT="$a"
  [[ "$prev" == "--data-binary" ]] && REQUEST="${a#@}"
  prev="$a"
done
if [[ -n "${SHIM_CAPTURE_BODY:-}" && -n "$REQUEST" ]]; then
  cp "$REQUEST" "$SHIM_CAPTURE_BODY"
fi
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

# The previous 10-call ceiling no longer prevents additional branding assets.
echo 10 > "$CAP_FILE"
echo 0 > "$TMP/shim.state"
ARGS=("prompt" "1:1" "$TMP/expanded-budget.png")
if run_gen env PATH="$SHIM:$PATH" SHIM_CODES=200 SHIM_STATE="$TMP/shim.state" \
    GEMINI_API_KEY=dummy >/dev/null 2>&1 && [[ "$(cat "$CAP_FILE")" == "11" ]]; then
  ok "default budget permits calls beyond the old 10-call cap"
else
  bad "default budget permits calls beyond the old 10-call cap"
fi

# Two callers racing for the final slot must not overspend the cap.
echo 23 > "$CAP_FILE"
echo 0 > "$TMP/shim.state"
ARGS=("prompt" "1:1" "$TMP/concurrent.png")
run_gen env PATH="$SHIM:$PATH" SHIM_CODES=200 SHIM_STATE="$TMP/shim.state" \
  GEMINI_API_KEY=dummy >"$TMP/caller1.log" 2>&1 &
CALLER1=$!
run_gen env PATH="$SHIM:$PATH" SHIM_CODES=200 SHIM_STATE="$TMP/shim.state" \
  GEMINI_API_KEY=dummy >"$TMP/caller2.log" 2>&1 &
CALLER2=$!
STATUS1=0; wait "$CALLER1" || STATUS1=$?
STATUS2=0; wait "$CALLER2" || STATUS2=$?
if [[ "$((STATUS1 + STATUS2))" == "3" && "$(cat "$CAP_FILE")" == "24" && "$(cat "$TMP/shim.state")" == "1" ]]; then
  ok "concurrent callers share the final budget slot safely"
else
  bad "concurrent budget (statuses: $STATUS1 $STATUS2, count: $(cat "$CAP_FILE"), requests: $(cat "$TMP/shim.state"))"
fi

# References are sent inline, and large payloads travel through a request file.
python3 - "$TMP/reference.png" <<'PY'
from PIL import Image
import os, sys
Image.frombytes('RGB', (300, 300), os.urandom(300*300*3)).save(sys.argv[1])
PY
rm -f "$CAP_FILE"
echo 0 > "$TMP/shim.state"
ARGS=("use this exact logo" "1:1" "$TMP/referenced.png" --reference "$TMP/reference.png")
if run_gen env PATH="$SHIM:$PATH" SHIM_CODES=200 SHIM_STATE="$TMP/shim.state" \
    SHIM_CAPTURE_BODY="$TMP/request.json" GEMINI_API_KEY=dummy >/dev/null 2>&1 \
    && jq -e '.contents[0].parts[1].inlineData | .mimeType == "image/png" and (.data | length > 131072)' "$TMP/request.json" >/dev/null \
    && [[ "$(cat "$CAP_FILE")" == "1" ]]; then
  ok "reference image payload above argument-size limit reaches HTTP through a file"
else
  bad "reference image payload above argument-size limit reaches HTTP through a file"
fi
rm -f "$CAP_FILE"
ARGS=("prompt" "1:1" "$TMP/out.png" --reference "$TMP/reference.png" --dry-run)
if OUT="$(run_gen env 2>/dev/null)" \
    && jq -e '.body.contents[0].parts[1].inlineData.mimeType == "image/png"' <<<"$OUT" >/dev/null \
    && [[ ! -e "$CAP_FILE" ]]; then
  ok "reference dry-run needs no key and does not charge the cap"
else
  bad "reference dry-run needs no key and does not charge the cap"
fi
ARGS=("prompt" "1:1" "$TMP/out.png" --reference "$TMP/missing.png" --dry-run)
if run_gen env >/dev/null 2>&1; then
  bad "missing reference rejected"
else
  ok "missing reference rejected"
fi
ARGS=("prompt" "1:1" "$TMP/out.png" --reference)
if run_gen env >/dev/null 2>&1; then
  bad "reference option without path rejected"
else
  ok "reference option without path rejected"
fi

echo ""
echo "Results: $PASS passed, $FAIL failed"
[[ $FAIL -eq 0 ]]
