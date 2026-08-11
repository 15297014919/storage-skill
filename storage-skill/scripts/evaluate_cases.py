#!/usr/bin/env python3
"""Run storage-selection fixtures and compare deterministic reports with golden assertions."""
import argparse
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REQUIRED_REPORT_KEYS = {"report_version", "recommendation", "alternatives", "rejections", "decision_trace", "risks", "validation_plan", "evidence", "pending_verifications"}


def check(name, passed, expected, actual):
    return {"name": name, "passed": passed, "expected": expected, "actual": actual}


def valid_report_contract(report):
    if not REQUIRED_REPORT_KEYS.issubset(report):
        return False
    recommendation = report.get("recommendation", {})
    if not isinstance(recommendation.get("components"), list) or not recommendation["components"]:
        return False
    if recommendation.get("confidence") not in {"high", "medium", "low"}:
        return False
    for item in report.get("risks", []):
        if not {"code", "severity", "description", "mitigation"}.issubset(item) or item["severity"] not in {"P0", "P1", "P2"}:
            return False
    for item in report.get("validation_plan", []):
        if not {"topic", "environment", "metric", "pass_criteria", "stop_condition"}.issubset(item) or item["environment"] not in {"staging", "read_only"}:
            return False
    return bool(report.get("validation_plan")) and bool(report.get("evidence"))


def compare(case, report):
    # codeflicker-fix: COMPAT-Issue-001/d8mms5q7xd5xjg3mo5qm
    golden = case["golden"]
    primary = set(report["recommendation"]["components"])
    rejection_codes = {item["reason_code"] for item in report["rejections"]}
    risk_codes = {item["code"] for item in report["risks"]}
    validation_topics = {item["topic"] for item in report["validation_plan"]}
    checks = []

    checks.append(check("source_case_preserved", bool(case.get("request")) and isinstance(case.get("expected"), dict), "保留 request 与 expected", {"has_request": bool(case.get("request")), "has_expected": isinstance(case.get("expected"), dict)}))

    checks.append(check("report_contract", valid_report_contract(report), "完整报告结构与字段枚举", sorted(report)))
    required = set(golden["required_primary_components"])
    checks.append(check("required_primary_components", required.issubset(primary), sorted(required), sorted(primary)))
    forbidden = set(golden["forbidden_primary_components"])
    checks.append(check("forbidden_primary_components", primary.isdisjoint(forbidden), sorted(forbidden), sorted(primary)))
    expected_rejections = set(golden["required_rejection_codes"])
    checks.append(check("required_rejection_codes", expected_rejections.issubset(rejection_codes), sorted(expected_rejections), sorted(rejection_codes)))
    expected_risks = set(golden["required_risk_codes"])
    checks.append(check("required_risk_codes", expected_risks.issubset(risk_codes), sorted(expected_risks), sorted(risk_codes)))
    expected_topics = set(golden["required_validation_topics"])
    checks.append(check("required_validation_topics", expected_topics.issubset(validation_topics), sorted(expected_topics), sorted(validation_topics)))
    minimum = golden["minimum_evidence_count"]
    checks.append(check("minimum_evidence_count", len(report["evidence"]) >= minimum, minimum, len(report["evidence"])))
    failures = [f"{item['name']}: expected={item['expected']}, actual={item['actual']}" for item in checks if not item["passed"]]
    return {"case_id": case["id"], "passed": not failures, "checks": checks, "failures": failures}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=Path(__file__).resolve().parents[1], type=Path)
    parser.add_argument("--artifacts-dir", type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    artifacts = args.artifacts_dir or root / "artifacts" / "eval" / timestamp
    artifacts.mkdir(parents=True, exist_ok=False)
    cases = sorted((root / "cases").glob("**/*.json"))
    results = []
    for case_path in cases:
        case = json.loads(case_path.read_text(encoding="utf-8"))
        case_dir = artifacts / case["id"]
        case_dir.mkdir()
        shutil.copy2(case_path, case_dir / "input.json")
        report_path = case_dir / "report.json"
        subprocess.run([sys.executable, str(root / "scripts" / "run_selection.py"), "--input", str(case_path), "--output", str(report_path)], check=True)
        report = json.loads(report_path.read_text(encoding="utf-8"))
        result = compare(case, report)
        (case_dir / "comparison.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        results.append(result)
    passed = sum(item["passed"] for item in results)
    summary = {"total": len(results), "passed": passed, "failed": len(results) - passed, "pass_rate": round(passed / len(results) * 100, 1) if results else 0, "results": results}
    (artifacts / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = ["# 存储选型评测报告", "", f"- 总案例数：{summary['total']}", f"- 通过：{summary['passed']}", f"- 失败：{summary['failed']}", f"- 通过率：{summary['pass_rate']}%", ""]
    for result in results:
        lines.append(f"## {'通过' if result['passed'] else '失败'}：{result['case_id']}")
        lines += [f"- {failure}" for failure in result["failures"]] or ["- 所有金标断言均满足。"]
        lines.append("")
    (artifacts / "summary.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"评测产物：{artifacts}")
    print(f"总数：{summary['total']}，通过：{summary['passed']}，失败：{summary['failed']}，通过率：{summary['pass_rate']}%")
    for result in results:
        print(f"{'PASS' if result['passed'] else 'FAIL'} {result['case_id']}")
        for failure in result["failures"]:
            print(f"  - {failure}")
    raise SystemExit(0 if summary["failed"] == 0 else 1)


if __name__ == "__main__":
    main()
