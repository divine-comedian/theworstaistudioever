#!/usr/bin/env bash
# Generate one image via the Gemini API (Nano Banana 2).
#
# Usage: gen-image.sh <prompt> <aspect> <out-path> [--dry-run]
#   <aspect> is one of the API-supported ratios (1:1, 16:9, ...).
#   --dry-run prints the request JSON to stdout; no network call, no counter.
#
# Env: GEMINI_API_KEY (required unless --dry-run; falls back to repo .env),
#      GEMINI_IMAGE_MODEL (optional model override),
#      GEN_IMAGE_ENV_FILE / GEN_IMAGE_STATE_DIR (test overrides).
#
# Hard cap: 10 API calls per UTC day, counted in state/runs/<date>.imagegen.
# At the cap, exits non-zero with IMAGEGEN_CAP_REACHED on stderr.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

fail() { echo "gen-image: $*" >&2; exit 1; }

DRY_RUN=0
POSITIONAL=()
for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY_RUN=1 ;;
    *) POSITIONAL+=("$arg") ;;
  esac
done

if [[ ${#POSITIONAL[@]} -ne 3 ]]; then
  echo "usage: $0 <prompt> <aspect> <out-path> [--dry-run]" >&2
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

BODY="$(jq -n --arg prompt "$PROMPT" --arg aspect "$ASPECT" '{
  contents: [{parts: [{text: $prompt}]}],
  generationConfig: {
    responseModalities: ["IMAGE"],
    imageConfig: {aspectRatio: $aspect}
  }
}')"

if [[ "$DRY_RUN" == "1" ]]; then
  jq -n --arg model "$MODEL" --arg url "$URL" --argjson body "$BODY" \
    '{model: $model, url: $url, body: $body}'
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

# Daily cap: refuse once 10 calls have been made this UTC day
STATE_DIR="${GEN_IMAGE_STATE_DIR:-$REPO_ROOT/state/runs}"
mkdir -p "$STATE_DIR"
CAP_FILE="$STATE_DIR/$(date -u +%F).imagegen"
COUNT="$(cat "$CAP_FILE" 2>/dev/null || echo 0)"
if [[ "$COUNT" -ge 10 ]]; then
  echo "gen-image: IMAGEGEN_CAP_REACHED ($COUNT calls today)" >&2
  exit 3
fi
echo $((COUNT + 1)) > "$CAP_FILE"

# Call the API; one mechanical retry with backoff on 429/5xx
RESPONSE_FILE="$(mktemp)"
trap 'rm -f "$RESPONSE_FILE"' EXIT
for attempt in 1 2; do
  HTTP_CODE="$(curl -sS -o "$RESPONSE_FILE" -w '%{http_code}' \
    -X POST "$URL" \
    -H "x-goog-api-key: ${GEMINI_API_KEY}" \
    -H "Content-Type: application/json" \
    --data "$BODY" || echo 000)"
  if [[ "$HTTP_CODE" == "200" ]]; then
    break
  fi
  if [[ "$attempt" == "1" && ( "$HTTP_CODE" == "429" || "$HTTP_CODE" =~ ^5 || "$HTTP_CODE" == "000" ) ]]; then
    echo "gen-image: HTTP $HTTP_CODE — retrying in 10s" >&2
    sleep 10
    continue
  fi
  fail "API call failed with HTTP $HTTP_CODE: $(head -c 500 "$RESPONSE_FILE")"
done

# Decode the base64 inlineData image part
if ! jq -er '[.candidates[0].content.parts[] | select(.inlineData.data) | .inlineData.data][0]' \
     "$RESPONSE_FILE" > "${RESPONSE_FILE}.b64" 2>/dev/null; then
  fail "response contains no image data: $(head -c 500 "$RESPONSE_FILE")"
fi
base64 -d "${RESPONSE_FILE}.b64" > "$OUT_PATH"
rm -f "${RESPONSE_FILE}.b64"
[[ -s "$OUT_PATH" ]] || fail "decoded image is empty"

echo "gen-image: wrote $OUT_PATH"
