#!/usr/bin/env python3
"""Validate declared brand kits; historical entries without a kit still pass."""

from html.parser import HTMLParser
import json
from pathlib import Path
import sys
import xml.etree.ElementTree as ET


class BrandReferences(HTMLParser):
    def __init__(self, content):
        super().__init__()
        self.images = set()
        self.icons = set()
        self.feed(content)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "img":
            self.images.add(attrs.get("src", "").removeprefix("./"))
        if tag == "link" and "icon" in attrs.get("rel", "").lower().split():
            self.icons.add(attrs.get("href", "").removeprefix("./"))


def require(condition, message):
    if not condition:
        raise ValueError(message)


def text_fields(obj, fields, label):
    require(isinstance(obj, dict), f"{label} must be an object")
    for name in fields:
        require(isinstance(obj.get(name), str) and obj[name].strip(), f"{label}.{name} is required")


def asset(entry, name):
    require(isinstance(name, str) and name.strip(), "asset filename is required")
    path = entry / name
    require(not Path(name).is_absolute() and path.resolve().is_relative_to(entry.resolve()), f"asset path escapes entry: {name}")
    require(path.is_file(), f"missing logo file or graphic asset: {name}")
    require(0 < path.stat().st_size <= 512000, f"asset must be nonempty and <=500 KB: {name}")
    return path


def validate(entry):
    concept = json.loads((entry / "concept.json").read_text())
    if "brand_kit" not in concept:
        return  # The archived catalogue predates this contract.
    kit = concept["brand_kit"]
    require(isinstance(kit, dict) and type(kit.get("version")) is int and kit["version"] in (1, 2), "brand_kit.version must be 1 or 2")
    text_fields(kit, ["identity_rationale"], "brand_kit")
    logo = kit.get("logo")
    text_fields(logo, ["concept", "primary_file", "mono_file", "icon_file", "clear_space", "placement"], "brand_kit.logo")
    require(type(logo.get("min_size_px")) is int and logo["min_size_px"] > 0, "logo.min_size_px must be a positive integer")
    files = [logo[key] for key in ["primary_file", "mono_file", "icon_file"]]
    require(len(set(files)) == 3, "logo needs separate primary, monochrome and icon files")
    for name in files:
        path = asset(entry, name)
        require(path.suffix.lower() in {".svg", ".png", ".webp", ".jpg", ".jpeg"}, f"unsupported logo format: {name}")
        if path.suffix.lower() == ".svg":
            root = ET.fromstring(path.read_text())
            require(root.tag.split("}")[-1] == "svg" and root.get("viewBox"), f"SVG logo needs an svg root and viewBox: {name}")
    if kit["version"] == 1:
        require(all(Path(logo[key]).suffix.lower() == ".svg" for key in ["mono_file", "icon_file"]), "version 1 monochrome and icon logos must be SVG")
    text_fields(kit.get("graphic_language"), ["medium", "motif", "composition", "texture"], "brand_kit.graphic_language")
    text_fields(kit.get("tokens"), ["spacing", "radii", "borders", "shadows"], "brand_kit.tokens")
    plan = kit.get("graphic_plan")
    require(isinstance(plan, list) and len(plan) >= 2, "brand_kit needs at least two supporting graphic plans")
    for item in plan:
        text_fields(item, ["role", "purpose", "placement", "medium"], "brand_kit.graphic_plan item")
    for page in ["index.html", "demo.html"]:
        refs = BrandReferences((entry / page).read_text())
        require(bool({logo["primary_file"], logo["mono_file"]} & refs.images), f"{page} must display the primary or monochrome logo")
        require(logo["icon_file"] in refs.icons, f"{page} must use the brand icon favicon")
    if kit["version"] == 2:
        generation = kit.get("generation")
        require(isinstance(generation, dict) and generation.get("mode") in ("gemini", "mixed", "fallback"), "brand_kit.generation.mode must be gemini, mixed or fallback")
        if generation["mode"] == "fallback":
            text_fields(generation, ["fallback_reason"], "brand_kit.generation")
            return
        if generation["mode"] == "mixed":
            text_fields(generation, ["revision_reason"], "brand_kit.generation")
        items = (concept.get("images") or {}).get("items", [])
        require(isinstance(items, list) and all(isinstance(item, dict) for item in items), "image provenance items must be objects")
        records = {item.get("file"): item for item in items}

        def gemini_origin(name, allow_revision=False):
            seen = set()
            while name not in seen:
                seen.add(name)
                record = records.get(name, {})
                if record.get("source") == "gemini":
                    require(asset(entry, name).suffix.lower() in {".png", ".webp", ".jpg", ".jpeg"}, "Gemini source must be a raster image")
                    return
                if allow_revision and record.get("source") == "openai-imagegen":
                    require(record.get("tool") == "image_gen", "replacement artwork must identify image_gen tool provenance")
                    text_fields(record, ["prompt"], "replacement artwork")
                    require(asset(entry, name).suffix.lower() in {".png", ".webp", ".jpg", ".jpeg"}, "replacement artwork must be raster")
                    return
                require(record.get("source") == "derived-export", f"{name} must have Gemini design provenance")
                asset(entry, name)
                name = record.get("source_file")
                require(isinstance(name, str), "derived export needs source_file")
            raise ValueError("cyclic derived-export provenance")

        gemini_origin(logo["primary_file"])
        landing = BrandReferences((entry / "index.html").read_text())
        graphic_files = set()
        for item in plan:
            require(item.get("role") in {"graphic-design", "infographic"}, "version 2 requires composed graphic-design or infographic assets; photography/basic diagrams do not count")
            name = item.get("file")
            asset(entry, name)
            gemini_origin(name, allow_revision=generation["mode"] == "mixed")
            require(records.get(name, {}).get("role") in {"graphic-design", "infographic"}, f"{name} must have a graphic-design provenance role")
            require(name in landing.images, f"index.html must display graphic artwork: {name}")
            graphic_files.add(name)
        require(len(graphic_files) >= 2, "two distinct graphic artworks are required")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: validate-brand-kit.py <entry-directory>")
    try:
        validate(Path(sys.argv[1]))
    except (ValueError, OSError, ET.ParseError) as exc:
        sys.exit(f"brand kit: {exc}")
