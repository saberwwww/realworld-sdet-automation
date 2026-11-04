"""Summarize real pytest JUnit XML without additional reporting dependencies."""
import argparse
import json
from pathlib import Path
import xml.etree.ElementTree as ET


def summarize(path):
    root = ET.parse(path).getroot()
    suites = [root] if root.tag == "testsuite" else list(root.iter("testsuite"))
    totals = {key: sum(int(suite.get(key, 0)) for suite in suites)
              for key in ("tests", "failures", "errors", "skipped")}
    totals["passed"] = totals["tests"] - totals["failures"] - totals["errors"] - totals["skipped"]
    totals["seconds"] = round(sum(float(suite.get("time", 0)) for suite in suites), 3)
    cases = []
    for case in root.iter("testcase"):
        status, reason = "passed", ""
        for tag in ("error", "failure", "skipped"):
            node = case.find(tag)
            if node is not None:
                status, reason = tag, node.get("message", "")
                break
        cases.append({"name": case.get("classname", "") + "::" + case.get("name", ""),
                      "status": status, "reason": reason, "seconds": float(case.get("time", 0))})
    return {"source": str(path), "totals": totals, "cases": cases}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("xml", nargs="+", type=Path)
    args = parser.parse_args()
    print(json.dumps([summarize(path) for path in args.xml], ensure_ascii=False, indent=2))
