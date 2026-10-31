#!/usr/bin/env python3
"""Create a compact Markdown summary from downloaded JUnit XML reports."""
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
patterns = ("server/reports/*.xml", "languages/**/target/surefire-reports/*.xml", "reports/**/*.xml")
files = sorted({path for pattern in patterns for path in ROOT.glob(pattern)})
lines = ["# CI test summary", "", "| Report | Tests | Failures | Errors | Skipped |", "|---|---:|---:|---:|---:|"]
totals = [0, 0, 0, 0]
if not files:
    lines += ["| No JUnit XML artifacts found | — | — | — | — |", "", "Native test job logs remain the source of truth for suites that do not emit JUnit XML."]
else:
    for path in files:
        root = ET.parse(path).getroot()
        suites = [root] if root.tag == "testsuite" else list(root.iter("testsuite"))
        values = [sum(int(suite.attrib.get(key, "0")) for suite in suites) for key in ("tests", "failures", "errors", "skipped")]
        totals = [left + right for left, right in zip(totals, values)]
        lines.append(f"| {path.relative_to(ROOT)} | {values[0]} | {values[1]} | {values[2]} | {values[3]} |")
    lines += [f"| **Total (JUnit reports only)** | **{totals[0]}** | **{totals[1]}** | **{totals[2]}** | **{totals[3]}** |"]
lines += ["", "This summary includes only JUnit XML files uploaded by completed jobs. It is not a substitute for checking every language job's exit status."]
output = ROOT / "ci-test-summary.md"
output.write_text("\n".join(lines) + "\n", encoding="utf-8")
print(output.read_text(encoding="utf-8"))
