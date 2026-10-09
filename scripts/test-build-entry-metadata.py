#!/usr/bin/env python3
"""Regression tests for entry sharing previews; uses only temporary sites."""

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

from PIL import Image


spec = importlib.util.spec_from_file_location("metadata", Path(__file__).with_name("build-entry-metadata.py"))
metadata = importlib.util.module_from_spec(spec)
spec.loader.exec_module(metadata)


class MetadataTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.site = Path(self.temp.name)
        (self.site / "CNAME").write_text("preview.example.com\n")
        Image.new("RGB", (320, 320)).save(self.site / "logo.png")
        self.slug = "paypal-for-flat-earthers"
        self.entry = self.site / "entries" / self.slug
        self.entry.mkdir(parents=True)
        self.concept = {
            "product_name": "Edgewise",
            "tagline": "PayPal for flat-earthers",
            "one_liner": "This is deliberately different from the hero.",
            "hero": {
                "h1": "Money moves in straight lines.",
                "sub": "Edgewise is the first payments network built on the map you already trust. No curvature fees. No routing through hemispheres. Every transfer is held a regulation 40 feet back from the ice wall.",
            },
        }
        self.save_concept()
        self.body = '<body><h1>Money moves</h1><script>const x = "og:title";</script></body></html>\n'
        self.source = '''<!doctype html><html><HEAD>
<meta charset="utf-8"><meta name="viewport" content="width=device-width">
<TITLE>Old title</TITLE>
<meta NAME='description' content='old'>
<meta property='og:title' content='duplicate 1'/>
<meta property='og:title' content='duplicate 2'>
<meta name='twitter:card' content='summary'>
<link REL='canonical' href='https://old.example/'>
<link rel="stylesheet" href="fonts.css">
<!-- <meta property="og:title" content="comment"> -->
<style>.test:after { content: "<meta>"; }</style>
</HEAD>''' + self.body
        for name in ("index.html", "demo.html"):
            (self.entry / name).write_text(self.source)

    def save_concept(self):
        (self.entry / "concept.json").write_text(json.dumps(self.concept))

    def build(self):
        metadata.build(self.site, self.slug)
        metadata.build(self.site, self.slug, check=True)
        return metadata.Head((self.entry / "index.html").read_text()).values

    def test_edgewise_preview_uses_all_hero_copy(self):
        values = self.build()
        expected = self.concept["hero"]["h1"] + " " + self.concept["hero"]["sub"]
        self.assertEqual(values["title"], ["Edgewise — PayPal for flat-earthers"])
        for key in ("description", "og:description", "twitter:description"):
            self.assertEqual(values[key], [expected])
        self.assertEqual(values["og:url"], ["https://preview.example.com/entries/paypal-for-flat-earthers/"])

    def test_hero_image_provenance_and_absolute_url(self):
        Image.new("RGB", (1600, 900)).save(self.entry / "engraved chart.webp")
        self.concept["images"] = {"items": [{"role": "hero", "file": "engraved chart.webp"}]}
        self.save_concept()
        values = self.build()
        self.assertEqual(values["og:image"], ["https://preview.example.com/entries/paypal-for-flat-earthers/social-preview.jpg"])
        self.assertEqual(values["twitter:image"], values["og:image"])
        self.assertEqual(values["og:image:width"], ["1200"])
        self.assertEqual(values["og:image:height"], ["630"])
        self.assertEqual(values["og:image:type"], ["image/jpeg"])
        self.assertEqual(values["twitter:card"], ["summary_large_image"])
        with Image.open(self.entry / "social-preview.jpg") as image:
            self.assertEqual(image.size, (1200, 630))
            self.assertEqual(image.format, "JPEG")
        self.assertLessEqual((self.entry / "social-preview.jpg").stat().st_size, 512000)

    def test_image_less_entry_uses_logo(self):
        values = self.build()
        self.assertEqual(values["og:image"], ["https://preview.example.com/entries/paypal-for-flat-earthers/social-preview.jpg"])
        self.assertEqual(values["twitter:card"], ["summary_large_image"])
        self.assertEqual(values["og:image:alt"], ["The Worst AI Studio Ever logo"])

    def test_markup_whitespace_and_attribute_escaping(self):
        self.concept["hero"] = {"h1": 'Money<br>moves <em>straight</em>.', "sub": '  "Safe" &amp; <b>sound</b>.\n More. '}
        self.concept["product_name"] = 'Edge & "Wise"'
        self.save_concept()
        values = self.build()
        self.assertEqual(values["description"], ['Money moves straight. "Safe" & sound. More.'])
        self.assertEqual(values["og:title"], ['Edge & "Wise" — PayPal for flat-earthers'])
        self.assertIn('&quot;Safe&quot; &amp; sound.', (self.entry / "index.html").read_text())

    def test_truncation_at_word_boundary_and_exact_limit(self):
        self.concept["hero"] = {"h1": "Money moves.", "sub": "straight lines " * 50}
        self.save_concept()
        description = self.build()["description"][0]
        self.assertLessEqual(len(description), 300)
        self.assertTrue(description.endswith("…"))
        full = metadata.plain(self.concept["hero"]["h1"] + " " + self.concept["hero"]["sub"])
        self.assertTrue(full.startswith(description[:-1] + " "))
        self.assertEqual(metadata.truncate("x" * 300), "x" * 300)
        self.assertEqual(metadata.truncate("x" * 301), "x" * 299 + "…")

    def test_absent_hero_falls_back_to_one_liner(self):
        self.concept.pop("hero")
        self.save_concept()
        self.assertEqual(self.build()["description"], [self.concept["one_liner"]])

    def test_idempotence_and_preservation_of_page_content(self):
        self.build()
        before = [(self.entry / name).read_bytes() for name in ("index.html", "demo.html", "social-preview.jpg")]
        self.build()
        after = [(self.entry / name).read_bytes() for name in ("index.html", "demo.html", "social-preview.jpg")]
        self.assertEqual(before, after)
        for source in after[:2]:
            self.assertTrue(source.decode().endswith(self.body))
            self.assertIn('<meta charset="utf-8">', source.decode())
            self.assertIn('<style>.test:after { content: "<meta>"; }</style>', source.decode())
            self.assertIn('<link rel="stylesheet" href="fonts.css">', source.decode())

    def test_demo_has_its_own_canonical_url_and_title(self):
        self.build()
        values = metadata.Head((self.entry / "demo.html").read_text()).values
        self.assertEqual(values["canonical"], ["https://preview.example.com/entries/paypal-for-flat-earthers/demo.html"])
        self.assertEqual(values["og:url"], values["canonical"])
        self.assertEqual(values["twitter:title"], ["Edgewise — PayPal for flat-earthers — Demo"])

    def test_check_rejects_missing_duplicate_and_stale_tags(self):
        self.build()
        path = self.entry / "index.html"
        valid = path.read_text()
        for source in (
            valid.replace('name="twitter:card"', 'name="removed:card"'),
            valid.replace('</HEAD>', '<meta property="og:title" content="duplicate"></HEAD>'),
            valid.replace('Money moves in straight lines.', 'Stale description.'),
        ):
            path.write_text(source)
            with self.assertRaises(ValueError):
                metadata.build(self.site, self.slug, check=True)

    def test_malformed_demo_does_not_modify_landing(self):
        (self.entry / "demo.html").write_text('<html><body>missing head</body></html>')
        with self.assertRaises(ValueError):
            metadata.build(self.site, self.slug)
        self.assertEqual((self.entry / "index.html").read_text(), self.source)
        self.assertFalse((self.entry / "social-preview.jpg").exists())

    def test_check_rejects_missing_or_stale_preview_image(self):
        self.build()
        image = self.entry / "social-preview.jpg"
        image.unlink()
        with self.assertRaisesRegex(ValueError, "sharing image"):
            metadata.build(self.site, self.slug, check=True)
        image.write_bytes(b"stale")
        with self.assertRaisesRegex(ValueError, "sharing image"):
            metadata.build(self.site, self.slug, check=True)

    def test_hero_path_cannot_escape_entry(self):
        self.concept["images"] = {"items": [{"role": "hero", "file": "../../logo.png"}]}
        self.save_concept()
        with self.assertRaisesRegex(ValueError, "inside the entry"):
            metadata.build(self.site, self.slug)


if __name__ == "__main__":
    unittest.main()
