#!/usr/bin/env python3
"""Validate storage-skill repository contracts and regression fixtures."""
import json
import sys
from pathlib import Path

EXPECTED_PROFILES = {"ksql", "ktable", "redis", "kcache", "kiwi", "memcached", "kwaibase", "hbase", "elasticsearch", "clickhouse", "doris", "kafka", "btq", "kgraph"}
REQUIRED_YAML_FIELDS = ["name", "internal_name", "category", "platform", "data_model", "consistency", "scalability", "cost_profile", "sla", "query_patterns", "anti_patterns"]
REQUIRED_GOLDEN_KEYS = {"required_primary_components", "allowed_alternatives", "forbidden_primary_components", "required_rejection_codes", "required_risk_codes", "required_validation_topics", "minimum_evidence_count"}
REQUIRED_INPUT_KEYS = {"scenario", "data_model", "consistency", "query_patterns"}


def main():
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
    errors = []
    profiles = {path.stem for path in (root / "knowledge").glob("*.yaml")}
    missing_profiles = EXPECTED_PROFILES - profiles
    if missing_profiles:
        errors.append(f"Missing profiles: {sorted(missing_profiles)}")
    for path in (root / "knowledge").glob("*.yaml"):
        content = path.read_text(encoding="utf-8")
        for field in REQUIRED_YAML_FIELDS:
            if f"{field}:" not in content:
                errors.append(f"Profile {path.name} missing field: {field}")
    print(f"OK: {len(profiles)} profiles found")

    for schema in ["request.schema.json", "report.schema.json", "evaluation.schema.json"]:
        path = root / "schemas" / schema
        try:
            json.loads(path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError) as exc:
            errors.append(f"Invalid schema {schema}: {exc}")

    cases = sorted((root / "cases").glob("**/*.json"))
    if len(cases) < 8:
        errors.append(f"Expected >=8 cases, found {len(cases)}")
    kinds = {"typical": 0, "traps": 0}
    for path in cases:
        try:
            case = json.loads(path.read_text(encoding="utf-8"))
            kinds[case.get("kind")] = kinds.get(case.get("kind"), 0) + 1
            if not {"id", "kind", "request", "expected", "input", "golden"}.issubset(case):
                errors.append(f"Case {path.name}: missing source or machine-evaluation contract keys")
                continue
            if not REQUIRED_INPUT_KEYS.issubset(case["input"]):
                errors.append(f"Case {path.name}: input missing required keys")
            if not REQUIRED_GOLDEN_KEYS.issubset(case["golden"]):
                errors.append(f"Case {path.name}: golden missing required keys")
        except json.JSONDecodeError as exc:
            errors.append(f"Case {path.name}: JSON parse error: {exc}")
    if kinds.get("typical", 0) < 5 or kinds.get("traps", 0) < 3:
        errors.append(f"Expected >=5 typical and >=3 traps, found {kinds}")
    print(f"OK: {len(cases)} cases found ({kinds})")

    for path in [root / "SKILL.md", root / "prompts" / "main.md", root / "prompts" / "anti-pattern-check.md", root / "scripts" / "run_selection.py", root / "scripts" / "evaluate_cases.py"]:
        if not path.exists():
            errors.append(f"Missing: {path.relative_to(root)}")
    if errors:
        print("\nFAIL:")
        print("\n".join(f"- {error}" for error in errors))
        raise SystemExit(1)
    print("\nOK: Skill contracts and fixtures are valid!")


if __name__ == "__main__":
    main()
