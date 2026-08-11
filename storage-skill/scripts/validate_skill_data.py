#!/usr/bin/env python3
"""
Validate storage-skill data integrity.
Usage: python3 scripts/validate_skill_data.py <skill_root>
"""
import sys
import os
import json
import glob
from pathlib import Path

def err(msg):
    print(f"ERROR: {msg}", file=sys.stderr)

def main():
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path('.')

    # ---- Expected profiles (13 internal products) ----
    EXPECTED_PROFILES = {
        "ksql", "ktable",          # 关系型
        "redis", "kcache", "kiwi", "memcached",  # 缓存/KV
        "kwaibase", "hbase",       # 宽表
        "elasticsearch",           # 搜索
        "clickhouse", "doris",     # OLAP
        "kafka", "btq",            # 消息队列
        "kgraph",                  # 图
    }

    REQUIRED_YAML_FIELDS = [
        "name", "internal_name", "category", "platform",
        "data_model", "consistency", "scalability",
        "cost_profile", "sla", "query_patterns", "anti_patterns",
    ]

    REQUIRED_REPORT_KEYS = [
        "推荐方案", "推荐理由", "次优方案",
        "明确淘汰方案", "已识别风险与反模式",
        "验证建议", "引用来源", "待验证项",
    ]

    errors = []

    # 1. Check profiles
    knowledge_dir = root / "knowledge"
    if not knowledge_dir.exists():
        errors.append("knowledge/ directory missing")
    else:
        found_profiles = set()
        for yaml_file in sorted(knowledge_dir.glob("*.yaml")):
            name = yaml_file.stem
            found_profiles.add(name)
            content = yaml_file.read_text(encoding="utf-8")
            for field in REQUIRED_YAML_FIELDS:
                if field + ":" not in content:
                    errors.append(f"Profile {name}.yaml missing field: {field}")

        missing = EXPECTED_PROFILES - found_profiles
        if missing:
            errors.append(f"Missing profiles: {sorted(missing)}")

        extra = found_profiles - EXPECTED_PROFILES
        if extra:
            print(f"INFO: Extra profiles found (not required): {sorted(extra)}")

        print(f"OK: {len(found_profiles)} profiles found: {sorted(found_profiles)}")

    # 2. Check cases
    cases_dir = root / "cases"
    all_cases = list(cases_dir.glob("**/*.json")) if cases_dir.exists() else []
    if len(all_cases) < 8:
        errors.append(f"Expected ≥8 test cases, found {len(all_cases)}")
    else:
        print(f"OK: {len(all_cases)} cases found")

    for case_file in all_cases:
        try:
            data = json.loads(case_file.read_text(encoding="utf-8"))
            expected = data.get("expected", {})
            for key in REQUIRED_REPORT_KEYS:
                if key not in expected:
                    errors.append(f"Case {case_file.name}: missing expected key '{key}'")
        except json.JSONDecodeError as e:
            errors.append(f"Case {case_file.name}: JSON parse error: {e}")

    # 3. Check prompts
    for prompt in ["prompts/main.md", "prompts/anti-pattern-check.md"]:
        if not (root / prompt).exists():
            errors.append(f"Missing: {prompt}")

    # 4. Check references
    for ref in ["references/decision-rubric.md", "references/report-schema.md",
                "references/evidence-and-safety.md"]:
        if not (root / ref).exists():
            errors.append(f"Missing: {ref}")

    # 5. Check SKILL.md
    skill_md = root / "SKILL.md"
    if not skill_md.exists():
        errors.append("SKILL.md missing")
    else:
        text = skill_md.read_text(encoding="utf-8")
        for keyword in ["KSQL", "KCache", "KwaiBase", "硬约束", "工作流"]:
            if keyword not in text:
                errors.append(f"SKILL.md may be outdated: missing keyword '{keyword}'")

    # 6. Check for placeholder remnants
    for f in (root / "knowledge").glob("*.yaml"):
        content = f.read_text(encoding="utf-8")
        if "待内部证据确认" in content:
            errors.append(f"Placeholder 待内部证据确认 still in {f.name}")

    # Summary
    if errors:
        print(f"\nFAIL: {len(errors)} error(s):")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)
    else:
        print("\nOK: Skill is valid!")

if __name__ == "__main__":
    main()
