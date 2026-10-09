#!/usr/bin/env python3
"""Write or check crawler-readable sharing metadata for one entry's HTML pages."""

import argparse
import html
from io import BytesIO
import json
from html.parser import HTMLParser
from pathlib import Path
import re
import sys

from PIL import Image, ImageOps


DESCRIPTION_LIMIT = 300
SITE_NAME = "theworstaistudioever"
PREVIEW_FILE = "social-preview.jpg"
PREVIEW_SIZE = (1200, 630)


def preview_image(path, hero, background):
    """Export a broadly supported JPEG without adding an AI generation step."""
    canvas = Image.new("RGB", PREVIEW_SIZE, background)
    with Image.open(path) as source:
        source = ImageOps.exif_transpose(source).convert("RGBA")
        if hero:
            source = ImageOps.fit(source, PREVIEW_SIZE, method=Image.Resampling.LANCZOS)
            canvas.paste(source, (0, 0), source)
        else:
            source.thumbnail((550, 550), Image.Resampling.LANCZOS)
            position = ((1200 - source.width) // 2, (630 - source.height) // 2)
            canvas.paste(source, position, source)
    for quality in (85, 75, 65, 55):
        output = BytesIO()
        canvas.save(output, format="JPEG", quality=quality, optimize=True)
        if output.tell() <= 512000:
            return output.getvalue()
    raise ValueError("sharing image exceeds the 500 KB image budget")


class PlainText(HTMLParser):
    def __init__(self, value):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.feed(value)

    def handle_data(self, data):
        self.parts.append(data)

    def handle_starttag(self, tag, attrs):
        if tag in ("br", "p", "div"):
            self.parts.append(" ")

    def handle_endtag(self, tag):
        if tag in ("p", "div"):
            self.parts.append(" ")


def plain(value):
    return " ".join("".join(PlainText(value or "").parts).split())


def truncate(value):
    if len(value) <= DESCRIPTION_LIMIT:
        return value
    cut = value[:DESCRIPTION_LIMIT - 1]
    if value[DESCRIPTION_LIMIT - 1] != " " and " " in cut:
        cut = cut.rsplit(" ", 1)[0]
    return cut.rstrip() + "…"


class Head(HTMLParser):
    """Locate metadata spans without reserializing CSS, JS, or body markup."""

    def __init__(self, source):
        super().__init__(convert_charrefs=True)
        self.source = source
        self.lines = [0]
        self.lines.extend(m.end() for m in re.finditer("\n", source))
        self.in_head = False
        self.head_end = None
        self.title_start = None
        self.title_parts = []
        self.remove = []
        self.values = {}
        self.feed(source)
        if self.head_end is None or self.title_start is not None:
            raise ValueError("HTML needs a complete <head> and closed <title>")

    def source_offset(self):
        line, column = self.getpos()
        return self.lines[line - 1] + column

    def handle_starttag(self, tag, attrs):
        if tag == "head":
            self.in_head = True
        if not self.in_head:
            return
        start = self.source_offset()
        attrs = dict(attrs)
        key = None
        if tag == "title":
            self.title_start = start
            self.title_parts = []
        elif tag == "meta":
            key = (attrs.get("property") or attrs.get("name") or "").lower()
            if key == "description" or key.startswith(("og:", "twitter:")):
                self.values.setdefault(key, []).append(attrs.get("content", ""))
            else:
                key = None
        elif tag == "link" and "canonical" in attrs.get("rel", "").lower().split():
            key = "canonical"
            self.values.setdefault(key, []).append(attrs.get("href", ""))
        if key:
            self.remove.append((start, start + len(self.get_starttag_text())))

    handle_startendtag = handle_starttag

    def handle_data(self, data):
        if self.in_head and self.title_start is not None:
            self.title_parts.append(data)

    def handle_endtag(self, tag):
        if not self.in_head:
            return
        if tag == "title" and self.title_start is not None:
            end = self.source.index(">", self.source_offset()) + 1
            self.remove.append((self.title_start, end))
            self.values.setdefault("title", []).append("".join(self.title_parts))
            self.title_start = None
        elif tag == "head":
            self.head_end = self.source_offset()
            self.in_head = False


def entry_metadata(site, slug):
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", slug):
        raise ValueError("invalid entry slug")
    entry = site / "entries" / slug
    concept = json.loads((entry / "concept.json").read_text())
    title = f"{plain(concept['product_name'])} — {plain(concept['tagline'])}"
    hero = concept.get("hero") or {}
    description = truncate(plain(" ".join(filter(None, [hero.get("h1"), hero.get("sub")]))))
    if not description:
        description = truncate(plain(concept.get("one_liner")))
    if not description:
        raise ValueError("hero text or one_liner is required")
    cname = site / "CNAME"
    domain = cname.read_text().strip() if cname.exists() else "theworstaistudioever.com"
    if not re.fullmatch(r"[A-Za-z0-9.-]+", domain):
        raise ValueError("invalid CNAME domain")
    base = f"https://{domain}"
    url = f"{base}/entries/{slug}/"

    # Use the entry's hero when present; image-less entries share the studio logo.
    items = (concept.get("images") or {}).get("items", [])
    hero_file = next((item["file"] for item in items if item.get("role") == "hero"), None)
    if not hero_file and (entry / "hero.webp").is_file():
        hero_file = "hero.webp"
    image_path = entry / hero_file if hero_file else site / "logo.png"
    if hero_file and not image_path.resolve().is_relative_to(entry.resolve()):
        raise ValueError("hero image must stay inside the entry directory")
    background = (concept.get("design_direction") or {}).get("palette", {}).get("bg", "#ffffff")
    image_bytes = preview_image(image_path, bool(hero_file), background)
    image_url = url + PREVIEW_FILE
    image_alt = f"{plain(concept['product_name'])} hero illustration" if hero_file else "The Worst AI Studio Ever logo"
    return {
        "title": title,
        "description": description,
        "canonical": url,
        "og:type": "website",
        "og:site_name": SITE_NAME,
        "og:title": title,
        "og:description": description,
        "og:url": url,
        "og:image": image_url,
        "og:image:type": "image/jpeg",
        "og:image:width": str(PREVIEW_SIZE[0]),
        "og:image:height": str(PREVIEW_SIZE[1]),
        "og:image:alt": image_alt,
        "twitter:card": "summary_large_image",
        "twitter:title": title,
        "twitter:description": description,
        "twitter:image": image_url,
        "twitter:image:alt": image_alt,
    }, image_bytes


def render(values):
    tags = []
    for key, value in values.items():
        value = html.escape(value, quote=True)
        if key == "title":
            tags.append(f"<title>{value}</title>")
        elif key == "canonical":
            tags.append(f'<link rel="canonical" href="{value}">')
        else:
            attr = "property" if key.startswith("og:") else "name"
            tags.append(f'<meta {attr}="{key}" content="{value}">')
    return "\n".join(tags)


def build(site, slug, check=False):
    metadata, image_bytes = entry_metadata(site, slug)
    image_path = site / "entries" / slug / PREVIEW_FILE
    if check and (not image_path.is_file() or image_path.read_bytes() != image_bytes):
        raise ValueError("missing or stale sharing image; run build-entry-metadata.py")
    pages = []
    for filename in ("index.html", "demo.html"):
        path = site / "entries" / slug / filename
        source = path.read_text()
        head = Head(source)
        values = dict(metadata)
        if filename == "demo.html":
            values["canonical"] += "demo.html"
            values["og:url"] = values["canonical"]
            for key in ("title", "og:title", "twitter:title"):
                values[key] += " — Demo"
        if check:
            for key, value in values.items():
                if head.values.get(key) != [value]:
                    raise ValueError(f"{filename}: missing, duplicate, or stale {key}; run build-entry-metadata.py")
            continue
        # Remove only metadata tags plus a following empty line when possible.
        prefix = source[:head.head_end]
        for start, end in sorted(head.remove, reverse=True):
            if prefix[end:end + 1] == "\n":
                end += 1
            prefix = prefix[:start] + prefix[end:]
        output = prefix.rstrip("\n") + "\n" + render(values) + "\n" + source[head.head_end:]
        pages.append((path, source, output))
    # Prepare both pages before writing either, so malformed input fails cleanly.
    if not check and (not image_path.exists() or image_path.read_bytes() != image_bytes):
        image_path.write_bytes(image_bytes)
    for path, source, output in pages:
        if output != source:
            path.write_text(output)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("site", type=Path)
    parser.add_argument("slug")
    parser.add_argument("--check", action="store_true", help="validate without writing")
    args = parser.parse_args()
    try:
        build(args.site, args.slug, args.check)
    except (ValueError, KeyError, OSError) as error:
        print(f"entry-metadata [{args.slug}]: {error}", file=sys.stderr)
        return 1
    print(f"entry-metadata [{args.slug}]: {'OK' if args.check else 'wrote landing + demo metadata'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
