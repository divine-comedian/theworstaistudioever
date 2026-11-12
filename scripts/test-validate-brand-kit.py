#!/usr/bin/env python3
"""Offline checks for brand assets, application, and historical compatibility."""

import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
import xml.etree.ElementTree as ET

from PIL import Image


SCRIPTS = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("brand_kit", SCRIPTS / "validate-brand-kit.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class BrandKitTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.site = Path(self.temp.name)
        self.entry = self.site / "entries/fixture-for-dogs"
        self.entry.mkdir(parents=True)
        Image.new("RGB", (64, 64), "navy").save(self.site / "logo.png")
        self.kit = {
            "version": 1,
            "identity_rationale": "A folded lead becomes a routing arrow.",
            "logo": {
                "concept": "Folded lead", "primary_file": "logo.svg",
                "mono_file": "logo-mono.svg", "icon_file": "logo-icon.svg",
                "clear_space": "Half the mark height", "min_size_px": 24,
                "placement": "Nav, footer and demo chrome",
            },
            "graphic_language": {"medium": "line illustration", "motif": "folds", "composition": "aligned grid", "texture": "none"},
            "tokens": {"spacing": "8px, 16px", "radii": "0px", "borders": "1px solid navy", "shadows": "none"},
            "graphic_plan": [
                {"role": "feature", "purpose": "Route a walk", "placement": "Feature section", "medium": "SVG"},
                {"role": "infographic", "purpose": "Show walk stages", "placement": "Explainer", "medium": "HTML/SVG"},
            ],
        }
        self.concept = {"date": "2026-11-06", "tagline": "Fixture for dogs", "product_name": "Lead",
                        "one_liner": "Walk scheduling", "design_direction": {"palette": {"bg": "#ffffff"}}, "brand_kit": self.kit}
        self.save()
        for name in ["logo.svg", "logo-mono.svg", "logo-icon.svg"]:
            (self.entry / name).write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32"><path fill="#123456" d="M4 4H28L4 28Z"/></svg>')
        self.html = '<!doctype html><html><head><link rel="icon" href="./logo-icon.svg"></head><body><img src="./logo.svg" alt="">' + '<p>Walk</p>' * 250 + '</body></html>'
        for name in ["index.html", "demo.html"]:
            (self.entry / name).write_text(self.html)

    def save(self):
        (self.entry / "concept.json").write_text(json.dumps(self.concept))

    def test_complete_kit_passes_entry_validator(self):
        subprocess.run(["python3", str(SCRIPTS / "build-entry-metadata.py"), str(self.site), self.entry.name], check=True, capture_output=True)
        result = subprocess.run(["bash", str(SCRIPTS / "validate-entry.sh"), str(self.site), self.entry.name], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_historical_entry_without_kit_passes(self):
        del self.concept["brand_kit"]
        self.save()
        (self.entry / "logo.svg").unlink()
        module.validate(self.entry)

    def test_missing_logo_fails(self):
        (self.entry / "logo-mono.svg").unlink()
        with self.assertRaisesRegex(ValueError, "missing logo file"):
            module.validate(self.entry)

    def test_malformed_svg_fails(self):
        (self.entry / "logo-mono.svg").write_text("<svg")
        with self.assertRaises(ET.ParseError):
            module.validate(self.entry)

    def test_svg_without_viewbox_fails(self):
        (self.entry / "logo-icon.svg").write_text("<svg/>")
        with self.assertRaisesRegex(ValueError, "viewBox"):
            module.validate(self.entry)

    def test_external_logo_fails(self):
        self.kit["logo"]["primary_file"] = "../outside.svg"
        self.save()
        with self.assertRaisesRegex(ValueError, "escapes entry"):
            module.validate(self.entry)

    def test_symlink_outside_entry_fails(self):
        path = self.entry / "logo.svg"
        path.unlink()
        path.symlink_to(self.site / "logo.png")
        with self.assertRaisesRegex(ValueError, "escapes entry"):
            module.validate(self.entry)

    def test_demo_must_display_logo(self):
        (self.entry / "demo.html").write_text(self.html.replace('<img src="./logo.svg" alt="">', ""))
        with self.assertRaisesRegex(ValueError, "demo.html must display"):
            module.validate(self.entry)

    def test_both_pages_must_use_icon(self):
        (self.entry / "index.html").write_text(self.html.replace('href="./logo-icon.svg"', 'href="/favicon.png"'))
        with self.assertRaisesRegex(ValueError, "index.html must use"):
            module.validate(self.entry)

    def test_monochrome_variant_can_be_displayed(self):
        (self.entry / "demo.html").write_text(self.html.replace('src="./logo.svg"', 'src="logo-mono.svg"'))
        module.validate(self.entry)

    def test_graphics_plan_required(self):
        self.kit["graphic_plan"].pop()
        self.save()
        with self.assertRaisesRegex(ValueError, "at least two"):
            module.validate(self.entry)

    def test_invalid_kit_rejected(self):
        for kit in [None, {}, {"version": 3}]:
            with self.subTest(kit=kit):
                self.concept["brand_kit"] = kit
                self.save()
                with self.assertRaisesRegex(ValueError, "brand_kit.version"):
                    module.validate(self.entry)

    def test_brand_failure_reaches_entry_validator(self):
        subprocess.run(["python3", str(SCRIPTS / "build-entry-metadata.py"), str(self.site), self.entry.name], check=True, capture_output=True)
        self.kit["graphic_plan"] = []
        self.save()
        result = subprocess.run(["bash", str(SCRIPTS / "validate-entry.sh"), str(self.site), self.entry.name], capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("brand kit validation failed", result.stderr)

    def make_gemini_kit(self):
        self.kit.update(version=2, generation={"mode": "gemini", "fallback_reason": ""})
        self.kit["logo"].update(primary_file="logo.png", mono_file="logo-mono.png", icon_file="logo-icon.png")
        items = []
        for name in ["logo.png", "logo-mono.png", "logo-icon.png", "campaign.webp", "infographic.webp"]:
            Image.new("RGB", (64, 64), "navy").save(self.entry / name)
            items.append({"file": name, "source": "gemini", "role": "logo" if name.startswith("logo") else "graphic-design"})
        self.concept["images"] = {"items": items}
        for item, name in zip(self.kit["graphic_plan"], ["campaign.webp", "infographic.webp"]):
            item.update(role="graphic-design", file=name)
        for page in ["index.html", "demo.html"]:
            content = self.html.replace('logo.svg', 'logo.png').replace('logo-icon.svg', 'logo-icon.png')
            if page == "index.html":
                content = content.replace('</body>', '<img src="campaign.webp"><img src="infographic.webp"></body>')
            (self.entry / page).write_text(content)
        self.save()

    def test_version_two_gemini_raster_identity_and_artwork_pass(self):
        self.make_gemini_kit()
        module.validate(self.entry)

    def test_explicit_mixed_revision_keeps_gemini_identity_and_honest_replacement_art(self):
        self.make_gemini_kit()
        self.kit['generation'].update(mode='mixed', revision_reason='User requested replacement of unclear artwork.')
        self.concept['images']['items'][-1].update(source='openai-imagegen', tool='image_gen', prompt='A specific framing comparison.')
        self.save()
        module.validate(self.entry)

    def test_replacement_art_cannot_claim_gemini_provenance_or_skip_revision_reason(self):
        self.make_gemini_kit()
        self.concept['images']['items'][-1].update(source='openai-imagegen', tool='image_gen', prompt='A framing comparison.')
        self.save()
        with self.assertRaisesRegex(ValueError, 'Gemini design provenance'):
            module.validate(self.entry)
        self.kit['generation']['mode'] = 'mixed'
        self.save()
        with self.assertRaisesRegex(ValueError, 'revision_reason'):
            module.validate(self.entry)

    def test_mixed_revision_does_not_waive_logo_or_tool_provenance(self):
        self.make_gemini_kit()
        self.kit['generation'].update(mode='mixed', revision_reason='Requested artwork repair.')
        self.concept['images']['items'][0].update(source='openai-imagegen', tool='image_gen', prompt='Replacement logo.')
        self.save()
        with self.assertRaisesRegex(ValueError, 'Gemini design provenance'):
            module.validate(self.entry)
        self.concept['images']['items'][0]['source'] = 'gemini'
        self.concept['images']['items'][-1].update(source='openai-imagegen', tool='unrecorded', prompt='Framing comparison.')
        self.save()
        with self.assertRaisesRegex(ValueError, 'tool provenance'):
            module.validate(self.entry)

    def test_explicit_logo_revision_requires_reason_and_honest_provenance(self):
        self.make_gemini_kit()
        self.kit['generation'].update(mode='mixed', revision_reason='Requested visual revision.',
                                      logo_revision_reason='User requested a logo matching the approved album artwork.')
        logo = self.concept['images']['items'][0]
        logo.update(source='openai-imagegen', tool='image_gen', prompt='Album-inspired Annex wordmark.')
        self.save()
        module.validate(self.entry)
        self.kit['generation']['logo_revision_reason'] = ''
        self.save()
        with self.assertRaisesRegex(ValueError, 'logo_revision_reason'):
            module.validate(self.entry)
        self.kit['generation']['logo_revision_reason'] = 'User requested a logo revision.'
        logo['tool'] = 'unrecorded'
        self.save()
        with self.assertRaisesRegex(ValueError, 'tool provenance'):
            module.validate(self.entry)

    def test_version_two_rejects_native_logo_as_gemini_design(self):
        self.make_gemini_kit()
        self.concept["images"]["items"][0]["source"] = "native-svg"
        self.save()
        with self.assertRaisesRegex(ValueError, "Gemini design provenance"):
            module.validate(self.entry)

    def test_version_two_rejects_photography_as_graphic_design(self):
        self.make_gemini_kit()
        self.concept["images"]["items"][-1]["role"] = "testimonial"
        self.save()
        with self.assertRaisesRegex(ValueError, "graphic-design provenance role"):
            module.validate(self.entry)

    def test_version_two_requires_artwork_in_landing_page(self):
        self.make_gemini_kit()
        page = self.entry / "index.html"
        page.write_text(page.read_text().replace('<img src="campaign.webp">', ''))
        with self.assertRaisesRegex(ValueError, "must display graphic artwork"):
            module.validate(self.entry)

    def test_version_two_faithful_export_can_trace_to_gemini(self):
        self.make_gemini_kit()
        self.concept["images"]["items"][0].update(source="derived-export", source_file="logo-master.png")
        Image.new("RGB", (64, 64), "navy").save(self.entry / "logo-master.png")
        self.concept["images"]["items"].append({"file": "logo-master.png", "source": "gemini", "role": "logo"})
        self.save()
        module.validate(self.entry)

    def test_version_two_cannot_hide_missing_gemini_artwork_as_fallback(self):
        self.make_gemini_kit()
        self.kit["generation"] = {"mode": "fallback", "fallback_reason": ""}
        self.save()
        with self.assertRaisesRegex(ValueError, "fallback_reason"):
            module.validate(self.entry)

    def test_version_two_actual_api_fallback_is_explicit(self):
        self.make_gemini_kit()
        self.kit["generation"] = {"mode": "fallback", "fallback_reason": "Gemini key unavailable"}
        self.concept["images"]["items"] = []
        self.save()
        module.validate(self.entry)


if __name__ == "__main__":
    unittest.main()
