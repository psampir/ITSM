# ai-generated: 85% - written with an assistant from CI-SPEC.md section 3; the matching rules were checked against the practice set's expected.json
"""bakeoff.py - scanner SARIF + a labels file -> a per-tool confusion matrix (CI-SPEC.md P-14 to P-23).

Standard library only: the grader runs it as `python3 -S -E bakeoff.py ...` on Python 3.13.

    python3 bakeoff.py --labels labels.json a.sarif b.sarif > bakeoff.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from urllib.parse import unquote

# The ten course classes and the CWEs that map onto them (CI-SPEC.md section 3.2).
CLASSES: dict[str, frozenset[int]] = {
    "secret": frozenset({259, 260, 321, 798}),
    "injection": frozenset({74, 77, 78, 79, 80, 88, 89, 90, 91, 94, 95, 96, 611, 776, 917, 943, 1336}),
    "deserialization": frozenset({502}),
    "weak-crypto": frozenset({261, 326, 327, 328, 330, 331, 338, 759, 760, 916}),
    "insecure-transport": frozenset({295, 297, 319, 322, 757}),
    "path-traversal": frozenset({22, 23, 35, 36, 73}),
    "ssrf": frozenset({918}),
    "vulnerable-dependency": frozenset({937, 1035, 1104, 1395}),
    "misconfiguration": frozenset({16, 215, 250, 489, 668, 732, 1188}),
    "access-control": frozenset({284, 285, 639, 862, 863}),
}

FIXED_TOOL_IDS = frozenset({"trivy", "grype", "osv-scanner", "gitleaks"})
SEMGREP_TOOL_NAMES = frozenset({
    "semgrep", "semgrep oss", "semgrep ce", "semgrep community edition", "semgrep pro",
})
TRIVY_TAG_CLASSES = {
    "vulnerability": "vulnerable-dependency",
    "secret": "secret",
    "misconfiguration": "misconfiguration",
}

CWE_RE = re.compile(r"(?<![A-Za-z0-9])cwe-(\d+)", re.IGNORECASE)
TOKEN_RE = re.compile(r"[A-Za-z0-9._-]+")
SEPARATOR_RE = re.compile(r"[-_.]+")


def is_int(value: object) -> bool:
    """A JSON integer: not a bool, not a float, not a string (CI-SPEC.md P-18)."""
    return isinstance(value, int) and not isinstance(value, bool)


def member(obj: object, key: str) -> object:
    """obj[key], with a null value counting as absent (P-16)."""
    if not isinstance(obj, dict):
        return None
    return obj.get(key)


def tool_id_of_run(run: object) -> str | None:
    """The P-15 tool id of a run, or None when the entry is not a run at all."""
    if not isinstance(run, dict):
        return None
    driver = member(member(run, "tool"), "driver")
    name = member(driver, "name")
    if not isinstance(name, str):
        return "unknown"
    stripped = name.strip()
    if not stripped:
        return "unknown"
    lowered = stripped.lower()
    if lowered in FIXED_TOOL_IDS:
        return lowered
    if lowered in SEMGREP_TOOL_NAMES:
        return "semgrep"
    slug = re.sub(r"[^a-z0-9]+", "-", lowered).strip("-")
    return slug or "unknown"


def tags_of(obj: object) -> tuple[str, ...]:
    """The string entries of obj.properties.tags (P-19)."""
    tags = member(member(obj, "properties"), "tags")
    if not isinstance(tags, list):
        return ()
    return tuple(tag for tag in tags if isinstance(tag, str))


def first_location(result: dict) -> dict | None:
    locations = result.get("locations")
    if not isinstance(locations, list) or not locations:
        return None
    location = locations[0]
    return location if isinstance(location, dict) else None


def result_uri(result: dict) -> str | None:
    """The artifactLocation.uri of the first location, or None (P-16)."""
    physical = member(first_location(result), "physicalLocation")
    uri = member(member(physical, "artifactLocation"), "uri")
    return uri if isinstance(uri, str) and uri else None


def result_lines(result: dict) -> tuple[int, int] | None:
    """(start, end) as P-18 gives them, or None when the result has no lines."""
    region = member(member(first_location(result), "physicalLocation"), "region")
    start = member(region, "startLine")
    if not is_int(start) or start < 1:
        return None
    end = member(region, "endLine")
    if not is_int(end):
        end = start
    if end < start:
        end = start
    return start, end


def path_in_set(uri: str, root: str) -> str | None:
    """The result's file inside the set (P-17), or None when the result is outside it."""
    path = unquote(uri)
    if path[:7].lower() == "file://":
        path = path[7:]
    if path.startswith("./"):
        path = path[2:]
    components = path.split("/")
    index = None
    for position, component in enumerate(components):
        if component == root:
            index = position
    if index is None:
        return None
    return "/".join(components[index:])


def rule_of(run: dict, result: dict) -> dict | None:
    """The first entry of the run's tool.driver.rules[] whose id equals the result's ruleId (P-19)."""
    rule_id = result.get("ruleId")
    if not isinstance(rule_id, str):
        return None
    rules = member(member(member(run, "tool"), "driver"), "rules")
    if not isinstance(rules, list):
        return None
    for rule in rules:
        if isinstance(rule, dict) and rule.get("id") == rule_id:
            return rule
    return None


def classes_of(run: dict, result: dict) -> set[str]:
    """The result's classes, from the first of P-19's rules (a)..(d) that gives any."""
    own_class = member(member(result, "properties"), "class")
    if isinstance(own_class, str) and own_class in CLASSES:
        return {own_class}

    tool_id = tool_id_of_run(run)
    rule = rule_of(run, result)
    rule_tags = tags_of(rule)

    if tool_id == "gitleaks":
        return {"secret"}
    if tool_id in ("grype", "osv-scanner"):
        return {"vulnerable-dependency"}
    if tool_id == "trivy":
        from_tags = {TRIVY_TAG_CLASSES[tag.lower()] for tag in rule_tags if tag.lower() in TRIVY_TAG_CLASSES}
        if from_tags:
            return from_tags

    cwes: set[int] = set()
    for tag in (*tags_of(result), *rule_tags):
        for match in CWE_RE.finditer(tag):
            cwes.add(int(match.group(1)))
    classes = {name for name, numbers in CLASSES.items() if numbers & cwes}
    return classes or {"other"}


def normalize_package(name: str) -> str:
    """PEP 503: lower case, every run of -, _ and . replaced by a single -."""
    return SEPARATOR_RE.sub("-", name.lower())


def packages_named(result: dict) -> frozenset[str]:
    """The normalised tokens of the result's message.text (P-20)."""
    text = member(member(result, "message"), "text")
    if not isinstance(text, str):
        return frozenset()
    names = set()
    for token in TOKEN_RE.findall(text):
        token = token.strip("._-")
        if token:
            names.add(normalize_package(token))
    return frozenset(names)


def suppressions_empty(value: object) -> bool:
    """P-16: absent, null, [] or {}, and false, 0 and "" count as empty."""
    if value is None:
        return True
    if isinstance(value, (list, dict)):
        return not value
    if value is False or value == 0 or value == "":
        return True
    return False


def collect_results(documents: list[dict], root: str) -> dict[str, list[dict]]:
    """The results of every tool, restricted to the set (P-15 to P-18)."""
    tools: dict[str, list[dict]] = {}
    for document in documents:
        runs = member(document, "runs")
        if not isinstance(runs, list):
            continue
        for run in runs:
            tool_id = tool_id_of_run(run)
            if tool_id is None:
                continue
            results = tools.setdefault(tool_id, [])
            run_results = member(run, "results")
            if not isinstance(run_results, list):
                continue
            for result in run_results:
                if not isinstance(result, dict):
                    continue
                kind = result.get("kind")
                if kind is not None and kind != "fail":
                    continue
                if not suppressions_empty(result.get("suppressions")):
                    continue
                uri = result_uri(result)
                if uri is None:
                    continue
                path = path_in_set(uri, root)
                if path is None:
                    continue
                lines = result_lines(result)
                rule_id = result.get("ruleId")
                results.append({
                    "file": path,
                    "rule": rule_id if isinstance(rule_id, str) else None,
                    "start": lines[0] if lines else None,
                    "end": lines[1] if lines else None,
                    "classes": classes_of(run, result),
                    "packages": packages_named(result),
                })
    return tools


def matches(result: dict, defect: dict) -> bool:
    """P-20: one result against one defect."""
    if result["file"] != defect.get("file"):
        return False
    defect_class = defect.get("class")
    if defect_class not in result["classes"]:
        return False
    if defect_class == "vulnerable-dependency":
        package = defect.get("package")
        if not isinstance(package, str):
            return False
        return normalize_package(package) in result["packages"]
    if result["start"] is None:
        return False
    start = defect.get("start_line")
    end = defect.get("end_line")
    if not is_int(start) or not is_int(end):
        return False
    return result["start"] <= end and start <= result["end"]


def scores(tp: int, fp: int, fn: int) -> dict[str, float | None]:
    """P-22: precision, recall and F1, null where their denominator is zero, rounded to four digits."""
    def ratio(numerator: int, denominator: int) -> float | None:
        return round(numerator / denominator, 4) if denominator else None

    return {
        "precision": ratio(tp, tp + fp),
        "recall": ratio(tp, tp + fn),
        "f1": ratio(2 * tp, 2 * tp + fp + fn),
    }


def confusion_matrix(labels: dict, sarif_documents: list[dict]) -> dict:
    """The matrix of P-21 and P-22 for the labels (P-14) and the parsed SARIF documents."""
    root = labels["set"]
    defects = [d for d in labels.get("defects") or [] if isinstance(d, dict)]
    tools = collect_results(sarif_documents, root)

    matrix: dict[str, dict] = {}
    for tool_id, results in tools.items():
        found: set[int] = set()
        false_positives: set[tuple] = set()
        for result in results:
            matched = False
            for index, defect in enumerate(defects):
                if matches(result, defect):
                    found.add(index)
                    matched = True
            if not matched:
                false_positives.add((result["rule"], result["file"], result["start"], result["end"]))
        tp = len(found)
        fp = len(false_positives)
        fn = len(defects) - tp
        matrix[tool_id] = {"tp": tp, "fp": fp, "fn": fn, **scores(tp, fp, fn)}

    return {"set": root, "defects": len(defects), "tools": matrix}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="per-tool confusion matrix of SARIF against labels (CI-SPEC.md P-23)")
    parser.add_argument("--labels", required=True, help="the labels file (P-14)")
    parser.add_argument("sarif", nargs="+", help="SARIF 2.1.0 files")
    args = parser.parse_args(argv)
    with open(args.labels, encoding="utf-8") as fh:
        labels = json.load(fh)
    documents = []
    for path in args.sarif:
        with open(path, encoding="utf-8") as fh:
            documents.append(json.load(fh))
    json.dump(confusion_matrix(labels, documents), sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
