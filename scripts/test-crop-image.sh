#!/usr/bin/env bash
# Tests for crop-image.py
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CROP="$SCRIPT_DIR/crop-image.py"
TMP="$(mktemp -d)"
trap "rm -rf $TMP" EXIT

PASS=0
FAIL=0

ok()   { echo "PASS: $1"; PASS=$((PASS + 1)); }
bad()  { echo "FAIL: $1"; FAIL=$((FAIL + 1)); }

# Fixtures: a 300x100 banded image (left red / middle green / right blue)
# and an 800x400 noise image (incompressible as PNG).
python3 - "$TMP" <<'PY'
import os, sys
from PIL import Image
tmp = sys.argv[1]
bands = Image.new("RGB", (300, 100))
px = bands.load()
for x in range(300):
    color = (255, 0, 0) if x < 100 else (0, 255, 0) if x < 200 else (0, 0, 255)
    for y in range(100):
        px[x, y] = color
bands.save(f"{tmp}/bands.png")
noise = Image.frombytes("RGB", (800, 400), os.urandom(800 * 400 * 3))
noise.save(f"{tmp}/noise.png")
PY

# Test 1: output has exactly the requested dimensions
if python3 "$CROP" "$TMP/noise.png" "$TMP/out1.webp" --width 200 --height 200 >/dev/null 2>&1 \
   && python3 -c "from PIL import Image; im = Image.open('$TMP/out1.webp'); assert im.size == (200, 200), im.size" 2>/dev/null; then
  ok "cover-crop to exact 200x200"
else
  bad "cover-crop to exact 200x200"
fi

# Test 2: format inferred from extension (webp and jpg)
if python3 -c "from PIL import Image; assert Image.open('$TMP/out1.webp').format == 'WEBP'" 2>/dev/null \
   && python3 "$CROP" "$TMP/noise.png" "$TMP/out2.jpg" --width 100 --height 100 >/dev/null 2>&1 \
   && python3 -c "from PIL import Image; assert Image.open('$TMP/out2.jpg').format == 'JPEG'" 2>/dev/null; then
  ok "output format inferred from extension"
else
  bad "output format inferred from extension"
fi

# Test 3: wide source cover-cropped to 1:1 keeps the center (green band)
if python3 "$CROP" "$TMP/bands.png" "$TMP/out3.png" --width 100 --height 100 >/dev/null 2>&1 \
   && python3 -c "
from PIL import Image
im = Image.open('$TMP/out3.png').convert('RGB')
assert im.size == (100, 100), im.size
r, g, b = im.getpixel((50, 50))
assert g > 200 and r < 60 and b < 60, (r, g, b)
r, g, b = im.getpixel((2, 2))
assert g > 200 and r < 60 and b < 60, (r, g, b)
" 2>/dev/null; then
  ok "cover-crop keeps center of wide source"
else
  bad "cover-crop keeps center of wide source"
fi

# Test 4: webp output is smaller than the noise PNG source
if python3 "$CROP" "$TMP/noise.png" "$TMP/out4.webp" --width 800 --height 400 >/dev/null 2>&1 \
   && python3 -c "
import os
assert os.path.getsize('$TMP/out4.webp') < os.path.getsize('$TMP/noise.png')
" 2>/dev/null; then
  ok "webp output smaller than noise png source"
else
  bad "webp output smaller than noise png source"
fi

# Test 5: --quality knob works (lower quality -> smaller or equal file)
if python3 "$CROP" "$TMP/noise.png" "$TMP/q40.webp" --width 400 --height 400 --quality 40 >/dev/null 2>&1 \
   && python3 "$CROP" "$TMP/noise.png" "$TMP/q95.webp" --width 400 --height 400 --quality 95 >/dev/null 2>&1 \
   && python3 -c "
import os
assert os.path.getsize('$TMP/q40.webp') <= os.path.getsize('$TMP/q95.webp')
" 2>/dev/null; then
  ok "--quality affects output size"
else
  bad "--quality affects output size"
fi

# Test 6: --delete-input removes the source file after a successful crop
cp "$TMP/bands.png" "$TMP/raw.png"
if python3 "$CROP" "$TMP/raw.png" "$TMP/out6.webp" --width 50 --height 50 --delete-input >/dev/null 2>&1 \
   && [[ ! -e "$TMP/raw.png" && -s "$TMP/out6.webp" ]]; then
  ok "--delete-input removes source after success"
else
  bad "--delete-input removes source after success"
fi

# Test 7: missing input file exits non-zero
if python3 "$CROP" "$TMP/does-not-exist.png" "$TMP/out6.webp" --width 100 --height 100 >/dev/null 2>&1; then
  bad "missing input exits non-zero"
else
  ok "missing input exits non-zero"
fi

echo ""
echo "Results: $PASS passed, $FAIL failed"
[[ $FAIL -eq 0 ]]
