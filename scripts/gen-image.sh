#!/usr/bin/env bash
# Generate one image via the Gemini API (Nano Banana 2).
#
# Usage: gen-image.sh <prompt> <aspect> <out-path> [--reference image] [--dry-run]
#   <aspect> is one of the API-supported ratios (1:1, 16:9, ...).
#   --reference attaches a PNG/JPEG/WebP for edits or visual consistency (up to 3).
#   --dry-run prints the request JSON to stdout; no network call, no counter.
#
# Env: GEMINI_API_KEY (required unless --dry-run; falls back to repo .env),
#      GEMINI_IMAGE_MODEL (optional model override),
#      GEMINI_IMAGE_DAILY_LIMIT (default 24 successful calls per UTC day),
#      GEN_IMAGE_ENV_FILE / GEN_IMAGE_STATE_DIR (test overrides).
#
# Daily cap: 24 successful calls by default, counted in state/runs/<date>.imagegen.
# At the cap, exits non-zero with IMAGEGEN_CAP_REACHED on stderr.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

fail() { echo "gen-image: $*" >&2; exit 1; }

DRY_RUN=0
POSITIONAL=()
REFERENCES=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) DRY_RUN=1; shift ;;
    --reference)
      [[ $# -ge 2 ]] || fail "--reference requires an image path"
      REFERENCES+=("$2"); shift 2 ;;
    *) POSITIONAL+=("$1"); shift ;;
  esac
done
[[ ${#REFERENCES[@]} -le 3 ]] || fail "at most 3 reference images are supported"

if [[ ${#POSITIONAL[@]} -ne 3 ]]; then
  echo "usage: $0 <prompt> <aspect> <out-path> [--reference image] [--dry-run]" >&2
  exit 2
fi

PROMPT="${POSITIONAL[0]}"
ASPECT="${POSITIONAL[1]}"
OUT_PATH="${POSITIONAL[2]}"

case "$ASPECT" in
  1:1|2:3|3:2|3:4|4:3|4:5|5:4|9:16|16:9|21:9) ;;
  *) fail "unsupported aspect ratio: $ASPECT" ;;
esac

MODEL="${GEMINI_IMAGE_MODEL:-gemini-3.1-flash-image}"
URL="https://generativelanguage.googleapis.com/v1beta/models/${MODEL}:generateContent"

REQUEST_FILE="$(mktemp)"
cleanup() {
  rm -f "$REQUEST_FILE"
  if [[ -n "${RESPONSE_FILE:-}" ]]; then
    rm -f "$RESPONSE_FILE" "${RESPONSE_FILE}.b64"
  fi
}
trap cleanup EXIT
# Use a request file: reference-image base64 can exceed the OS argument limit.
python3 - "$PROMPT" "$ASPECT" "${REFERENCES[@]}" > "$REQUEST_FILE" <<'PY'
import base64, json, sys
from pathlib import Path
parts = [{"text": sys.argv[1]}]
mime_types = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}
for filename in sys.argv[3:]:
    path = Path(filename)
    if path.suffix.lower() not in mime_types or not path.is_file():
        sys.exit(f"gen-image: reference must be an existing PNG, JPEG or WebP: {filename}")
    if not 0 < path.stat().st_size <= 5 * 1024 * 1024:
        sys.exit(f"gen-image: reference must be nonempty and <=5 MB: {filename}")
    parts.append({"inlineData": {"mimeType": mime_types[path.suffix.lower()], "data": base64.b64encode(path.read_bytes()).decode()}})
body = json.dumps({"contents": [{"parts": parts}], "generationConfig": {"responseModalities": ["IMAGE"], "imageConfig": {"aspectRatio": sys.argv[2]}}})
if len(body.encode()) > 20 * 1024 * 1024:
    sys.exit("gen-image: request exceeds 20 MB")
print(body)
PY

if [[ "$DRY_RUN" == "1" ]]; then
  jq --arg model "$MODEL" --arg url "$URL" \
    '{model: $model, url: $url, body: .}' "$REQUEST_FILE"
  exit 0
fi

# Load the repo .env if the key isn't already in the environment
ENV_FILE="${GEN_IMAGE_ENV_FILE:-$REPO_ROOT/.env}"
if [[ -z "${GEMINI_API_KEY:-}" && -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
fi
[[ -n "${GEMINI_API_KEY:-}" ]] || fail "GEMINI_API_KEY is not set (env or $ENV_FILE)"

# Serialize the budget check and charge, including across overlapping callers.
DAILY_LIMIT="${GEMINI_IMAGE_DAILY_LIMIT-24}"
[[ "$DAILY_LIMIT" =~ ^[1-9][0-9]{0,8}$ ]] || fail "GEMINI_IMAGE_DAILY_LIMIT must be a positive integer (up to 999999999)"
STATE_DIR="${GEN_IMAGE_STATE_DIR:-$REPO_ROOT/state/runs}"
mkdir -p "$STATE_DIR"
CAP_FILE="$STATE_DIR/$(date -u +%F).imagegen"
exec 8>"${CAP_FILE}.lock"
flock -x 8
COUNT="$(cat "$CAP_FILE" 2>/dev/null || echo 0)"
[[ "$COUNT" =~ ^(0|[1-9][0-9]{0,8})$ ]] || fail "invalid daily image counter: $CAP_FILE"
if [[ "$COUNT" -ge "$DAILY_LIMIT" ]]; then
  echo "gen-image: IMAGEGEN_CAP_REACHED ($COUNT/$DAILY_LIMIT successful calls today)" >&2
  exit 3
fi

# The counter charges for *successful* calls only, and is incremented after the
# request loop below. It exists to cap spend, and a 429/5xx returns no image and
# costs nothing. Charging for those let one Gemini overload window (2026-08-28:
# ten consecutive 503s) burn most of the day's budget on nothing.

# Call the API; up to 3 attempts with linear backoff on 429/5xx/timeout.
# A single retry was too thin for a model-overloaded window.
RETRY_BASE_SLEEP="${GEN_IMAGE_RETRY_BASE_SLEEP:-10}"
RESPONSE_FILE="$(mktemp)"
for attempt in 1 2 3; do
  HTTP_CODE="$(curl -sS -o "$RESPONSE_FILE" -w '%{http_code}' \
    -X POST "$URL" \
    -H "x-goog-api-key: ${GEMINI_API_KEY}" \
    -H "Content-Type: application/json" \
    --data-binary "@$REQUEST_FILE" || echo 000)"
  if [[ "$HTTP_CODE" == "200" ]]; then
    break
  fi
  if [[ "$attempt" -lt 3 && ( "$HTTP_CODE" == "429" || "$HTTP_CODE" =~ ^5 || "$HTTP_CODE" == "000" ) ]]; then
    SLEEP_FOR=$((RETRY_BASE_SLEEP * attempt))
    echo "gen-image: HTTP $HTTP_CODE — attempt $attempt/3 failed, retrying in ${SLEEP_FOR}s" >&2
    sleep "$SLEEP_FOR"
    continue
  fi
  fail "API call failed with HTTP $HTTP_CODE: $(head -c 500 "$RESPONSE_FILE")"
done

# The call succeeded, so charge it against the daily cap.
echo $((COUNT + 1)) > "$CAP_FILE"

# Decode the base64 inlineData image part
if ! jq -er '[.candidates[0].content.parts[] | select(.inlineData.data) | .inlineData.data][0]' \
     "$RESPONSE_FILE" > "${RESPONSE_FILE}.b64" 2>/dev/null; then
  fail "response contains no image data: $(head -c 500 "$RESPONSE_FILE")"
fi
base64 -d "${RESPONSE_FILE}.b64" > "$OUT_PATH"
rm -f "${RESPONSE_FILE}.b64"
[[ -s "$OUT_PATH" ]] || fail "decoded image is empty"

echo "gen-image: wrote $OUT_PATH"
