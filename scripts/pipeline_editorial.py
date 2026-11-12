"""Pre-asset concept review and private accounting for non-interactive Codex."""

from datetime import datetime, timezone
import json
import math
import re

from pipeline_qa import (REVIEW_SCHEMA, TEXT, StageFailure,
                         budget, object_schema, quality_floor_context, validate_copy_audit, validate_shape,
                         validate_verdict)


def array(items, minimum=0, maximum=None):
    result = {"type": "array", "items": items, "minItems": minimum}
    if maximum is not None:
        result["maxItems"] = maximum
    return result


CONCEPT_SCHEMA = object_schema({
    **{key: TEXT for key in ["date", "company", "subject", "tagline", "slug", "product_name",
                            "one_liner", "brand_voice_notes", "demo_screen_concept"]},
    "hero": object_schema({key: TEXT for key in ["h1", "sub", "primary_cta"]}),
    "features": array(object_schema({"title": TEXT, "blurb": TEXT}), 3, 3),
    "pricing_tiers": array(object_schema({
        "name": TEXT, "price": TEXT, "tagline": TEXT, "perks": array(TEXT, 2),
    }), 3, 3),
    "testimonials": array(object_schema({key: TEXT for key in ["quote", "name", "title"]}), 3, 3),
    "editorial_plan": object_schema({
        "observations": array(object_schema({key: TEXT for key in ["behavior", "mechanic", "consequence"]}), 3, 3),
        "source_product_patterns": array(TEXT, 4),
        "composition_plan": TEXT,
        "audience_design": object_schema({
            "references": array(object_schema({key: TEXT for key in ["reference", "cues", "application"]}), 2),
            "landing_application": TEXT,
            "demo_application": TEXT,
        }),
    }),
})


def validate_editorial_config(workspace, config):
    checkpoint = config.get("concept_checkpoint", {})
    if type(checkpoint.get("enabled", False)) is not bool:
        raise ValueError("concept_checkpoint.enabled must be boolean")
    if checkpoint.get("enabled"):
        for name in ("draft_timeout_seconds", "review_timeout_seconds", "repair_timeout_seconds"):
            value = checkpoint[name]
            if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
                raise ValueError(f"Concept {name} must be positive")
        if not (workspace / "pipelines/codex-v1/concept-qa.md").is_file():
            raise ValueError("Missing concept-qa.md")
    usage = config.get("usage", {})
    if not isinstance(usage, dict) or not isinstance(usage.get("max_stage_tokens", {}), dict):
        raise ValueError("Usage configuration and stage limits must be objects")
    if type(usage.get("require_events", False)) is not bool:
        raise ValueError("usage.require_events must be boolean")
    for value in [usage.get("max_total_tokens"), *usage.get("max_stage_tokens", {}).values()]:
        if value is not None and (type(value) is not int or value <= 0):
            raise ValueError("Usage limits must be positive integers or null")


class UsageLedger:
    """Post-turn usage admission checks, never a claim of a hard in-flight cap."""

    def __init__(self, run, config):
        self.path, self.config = run / "usage.json", config.get("usage", {})
        self.stages = []

    def admit(self):
        limit = self.config.get("max_total_tokens")
        if limit is not None and self.total >= limit:
            raise StageFailure("Codex token allowance exhausted; refusing another stage or publication")

    @property
    def total(self):
        return sum(stage["input_tokens"] + stage["output_tokens"] for stage in self.stages)

    def record(self, label, trace):
        fields = ("input_tokens", "cached_input_tokens", "output_tokens", "reasoning_output_tokens")
        counts = dict.fromkeys(fields, 0)
        events = 0
        for line in trace.read_text().splitlines():
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue  # stderr may share the trace; it is never a usage event.
            if not isinstance(event, dict) or event.get("type") != "turn.completed":
                continue
            usage = event.get("usage", {})
            if not isinstance(usage, dict) or not all(type(usage.get(key)) is int and usage[key] >= 0
                                                    for key in ("input_tokens", "output_tokens")):
                raise StageFailure("Invalid Codex usage event; refusing publication")
            for key in fields:
                value = usage.get(key, 0)
                if type(value) is not int or value < 0:
                    raise StageFailure("Invalid Codex usage event; refusing publication")
                counts[key] += value
            events += 1
        self.stages.append({"stage": label, "completed_turns": events, **counts})
        self.path.write_text(json.dumps({
            "stages": self.stages, "total_tokens": self.total,
            "accounting": "input + output; cached input and reasoning output are reported separately, not added twice",
            "limit_semantics": "post-turn admission; the current turn may exceed its allowance",
        }, indent=2) + "\n")
        limits = self.config.get("max_stage_tokens", {})
        limits_active = self.config.get("max_total_tokens") is not None or any(value is not None for value in limits.values())
        if not events and (self.config.get("require_events") or limits_active):
            raise StageFailure("Missing completed-turn usage; refusing publication")
        # Match an exact label, or its family (concept, generation, review, repair).
        limit = limits.get(label, limits.get(label.split("-")[0]))
        if limit is not None and counts["input_tokens"] + counts["output_tokens"] >= limit:
            raise StageFailure(f"Codex token allowance exhausted for {label}; refusing publication")
        self.admit()


def recent_digest(workspace):
    concepts = []
    for path in (workspace / "site/entries").glob("*/concept.json"):
        concept = json.loads(path.read_text())
        concepts.append(concept)
    result = []
    for concept in sorted(concepts, key=lambda item: (item.get("date", ""), item.get("slug", "")), reverse=True)[:7]:
        result.append({
            "slug": concept.get("slug"), "tagline": concept.get("tagline"),
            "hero": concept.get("hero"), "features": concept.get("features", []),
            "prices": [{"name": tier.get("name"), "price": tier.get("price")}
                       for tier in concept.get("pricing_tiers", [])],
            "testimonial_roles": [item.get("title") for item in concept.get("testimonials", [])],
            "observations": concept.get("editorial_plan", {}).get("observations", []),
            "composition": concept.get("editorial_plan", {}).get("composition_plan",
                            concept.get("design_direction", {}).get("hero_composition_notes", "")),
            "design_direction": concept.get("design_direction", {}),
            "graphic_language": concept.get("brand_kit", {}).get("graphic_language", {}),
            "logo_concept": concept.get("brand_kit", {}).get("logo", {}).get("concept", ""),
        })
    return result


def roll(workspace):
    """The documented deterministic date-seeded LCG, now owned by the host."""
    date = datetime.now(timezone.utc).date().isoformat()
    companies = json.loads((workspace / "seeds/companies.json").read_text())
    subjects = json.loads((workspace / "seeds/subjects.json").read_text())
    for values in (companies, subjects):
        if not isinstance(values, list) or not values or not all(isinstance(x, str) and x.strip() for x in values):
            raise ValueError("Seeds must be nonempty string arrays")
    history_path = workspace / "state/history.json"
    history = json.loads(history_path.read_text()) if history_path.exists() else []
    used = {(item.get("company"), item.get("subject")) for item in history}
    state = sum(map(ord, date)) * 104729 % (2 ** 31)
    for _ in range(20):
        state = (1103515245 * state + 12345) % (2 ** 31)
        company = companies[state % len(companies)]
        state = (1103515245 * state + 12345) % (2 ** 31)
        subject = subjects[state % len(subjects)]
        if (company, subject) not in used:
            slugify = lambda value: re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
            slug = f"{slugify(company)}-for-{slugify(subject)}"
            if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", slug):
                raise ValueError("Seed pair produces an invalid slug")
            if (workspace / "site/entries" / slug).exists():
                raise StageFailure("Rolled entry already exists outside history; refusing overwrite")
            return {"date": date, "company": company, "subject": subject, "slug": slug,
                    "tagline": f"{company} for {subject}"}
    raise StageFailure("EXHAUSTED: all rolled pairs already in history. add more seeds.")


def concept_checkpoint(workspace, bundle, config, run, invoke, deadline, allowance):
    checkpoint = config["concept_checkpoint"]
    identity = roll(workspace)
    recent = recent_digest(workspace)
    floor = quality_floor_context(workspace)[0]
    (run / "recent-entries.json").write_text(json.dumps(recent, indent=2) + "\n")
    schema = run / "concept-schema.json"
    schema.write_text(json.dumps(CONCEPT_SCHEMA, indent=2) + "\n")
    source = (workspace / "pipeline.md").read_text()
    # Only concept instructions; asset and implementation details belong to build.
    voice = source.split("## Voice", 1)[-1].split("## Step 1", 1)[0]
    concept_rules = source.split("## Step 2", 1)[-1].split("## Step 3", 1)[0]
    prompt = """HOST CONCEPT DRAFT CHECKPOINT. Return only the concept JSON matching
the schema. Use the fixed identity below; the host already rolled it. Read and
apply the frozen anti-ai-slop skill. Follow the voice and concept instructions.
Each subject is an animal or relatable kind of person; if this supplied subject
is invalid, report failure rather than inventing another pair. Include the
editorial_plan requested by the schema. Do not write files, generate assets,
build HTML, run git, inspect secrets, use apps, delegate, or publish. The host
will review and persist the approved brief. Recent entries are comparison data,
not templates. Keep this concept specific and understandable on first reading.
""" + voice + concept_rules + "\nFIXED IDENTITY:\n" + json.dumps(identity) + "\nRECENT DIGEST:\n" + json.dumps(recent) + "\nAPPROVED QUALITY FLOOR:\n" + json.dumps(floor)
    path = invoke(prompt, "concept-draft", budget(deadline, checkpoint["draft_timeout_seconds"]),
                  read_only=True, schema=schema)
    report_schema = json.loads(json.dumps(REVIEW_SCHEMA))
    for field in ("demo_test", "visual_audit", "quality_floor"):
        del report_schema["properties"][field]
        report_schema["required"].remove(field)
    report_schema["properties"]["findings"]["items"]["properties"]["file"]["enum"] = ["concept.json"]
    review_schema = run / "concept-review-schema.json"
    review_schema.write_text(json.dumps(report_schema, indent=2) + "\n")
    previous_ids = set()
    summary = {"status": "failed", "slug": identity["slug"], "reviews": []}
    try:
        for attempt in range(config["qa"]["max_repair_attempts"] + 1):
            concept = json.loads(path.read_text())
            validate_shape(concept, CONCEPT_SCHEMA)
            if any(concept[key] != value for key, value in identity.items()):
                raise StageFailure("Concept changed the fixed rolled identity; refusing publication")
            review_prompt = (bundle / "concept-qa.md").read_text() + "\nHOST CONTEXT:\n" + json.dumps({
                "concept": concept, "recent_entries": recent,
                "approved_quality_floor": floor,
                "previous_findings": sorted(previous_ids),
                "previous_reviews": summary["reviews"],
            })
            report_path = invoke(review_prompt, f"concept-review-{attempt}",
                                 budget(deadline, checkpoint["review_timeout_seconds"]),
                                 read_only=True, schema=review_schema)
            report = json.loads(report_path.read_text())
            validate_shape(report, report_schema)
            if report["slug"] != identity["slug"]:
                raise ValueError("Concept reviewer returned the wrong slug")
            validate_verdict(report, previous_ids)
            validate_copy_audit(report, concept)
            summary["reviews"].append(str(report_path))
            previous_ids |= {finding["id"] for finding in report["findings"]}
            if report["verdict"] == "pass":
                approved = run / "approved-concept.json"
                approved.write_text(json.dumps(concept, indent=2, ensure_ascii=False) + "\n")
                summary["status"] = "passed"
                return concept
            number = allowance.claim("concept")
            prompt = """HOST CONCEPT REPAIR. Return the revised concept JSON only.
Fix every reported finding against its acceptance condition; preserve the fixed
date/company/subject/slug/tagline and product name. Keep successful observations.
Change matching copy and the editorial plan consistently. Do not write files,
generate images, build pages, inspect secrets, use apps, delegate or publish.
""" + json.dumps({"concept": concept, "review": report}, ensure_ascii=False)
            repaired = invoke(prompt, f"concept-repair-{number}",
                              budget(deadline, checkpoint["repair_timeout_seconds"]),
                              read_only=True, schema=schema)
            updated = json.loads(repaired.read_text())
            if updated.get("product_name") != concept["product_name"]:
                raise StageFailure("Concept repair changed product identity; refusing publication")
            path = repaired
    finally:
        summary["repair_attempts"] = allowance.used
        (run / "concept-summary.json").write_text(json.dumps(summary, indent=2) + "\n")
