#!/usr/bin/env python3
"""
Classify flags_to_clean.json entries into actionable updates keyed by wikidata_id.

Outputs:
1) action_map.json                - machine-readable mapping
2) wikidata_action_map.py         - Python dictionary for direct import/use
3) action_summary.txt             - human-readable counts and samples

Action schema per wikidata_id:
{
    "actions": {
        "is_public": false,      # hide junk
        "category": "historical",# fix wrong category
        "is_verified": false      # mark ambiguous for review
    },
    "reasons": ["junk:political", "wrong_category:city->historical"],
    "confidence": 0.88
}
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


# High-confidence junk indicators by category.
JUNK_PATTERNS = {
    "sports": [
        r"\bfootball club\b",
        r"\bsoccer club\b",
        r"\bsports club\b",
        r"\bbasketball club\b",
        r"\bbaseball club\b",
        r"\bhockey club\b",
        r"\brugby club\b",
        r"\bcricket club\b",
        r"\bvolleyball club\b",
        r"\bhandball club\b",
        r"\bnational (football|soccer|basketball|baseball|hockey|rugby|cricket|volleyball|handball) team\b",
        r"\bice hockey team\b",
        r"\bathletic club\b",
        r"\bclub deportivo\b",
        r"\bclub de futbol\b",
        r"\bfutbol club\b",
        r"\bsports team\b",
    ],
    "political": [
        r"\bpolitical party\b",
        r"\bpolitical movement\b",
        r"\bmovement\b",
        r"\bfront\b",
        r"\bcommunist party\b",
        r"\blabou?r party\b",
        r"\bliberal party\b",
        r"\bconservative party\b",
        r"\bgreen party\b",
        r"\bsocial democratic\b",
        r"\bchristian democratic\b",
        r"\bnational liberation front\b",
        r"\brhodesian front\b",
        r"\bnational movement\b",
        r"\bworkers'? party\b",
        r"\bpartido\b",
    ],
    "company": [
        r"\bcompany\b",
        r"\bcorporation\b",
        r"\bcorp\.?\b",
        r"\binc\.?\b",
        r"\bltd\.?\b",
        r"\bllc\b",
        r"\bplc\b",
        r"\bgmbh\b",
        r"\bs\.a\.\b",
        r"\bs\.p\.a\.\b",
        r"\bco\.\b",
        r"\bairline\b",
        r"\bshipping company\b",
        r"\bstate-owned enterprise\b",
    ],
    "milgov": [
        r"\bmilitary\b",
        r"\barmy\b",
        r"\bnavy\b",
        r"\bair force\b",
        r"\barmed forces\b",
        r"\bministry\b",
        r"\bdepartment\b",
        r"\bgovernment agency\b",
        r"\bagency\b",
        r"\bpolice\b",
        r"\bpolice department\b",
        r"\bintelligence service\b",
        r"\bintelligence agency\b",
        r"\bgendarmerie\b",
        r"\bnational guard\b",
        r"\bcoast guard\b",
        r"\bborder guard\b",
        r"\bborder service\b",
        r"\bfire and rescue\b",
        r"\bregiment\b",
        r"\barmoured regiment\b",
        r"\bartillery regiment\b",
        r"\bgrenadier regiment\b",
        r"\bhussar regiment\b",
        r"\binfantry regiment\b",
    ],
    "ethnic_human_group": [
        r"\bethnic group\b",
        r"\bindigenous people\b",
        r"\bhuman group\b",
        r"\btribe\b",
        r"\btribes\b",
        r"\bunited tribes\b",
        r"\bunrepresented nations and peoples\b",
    ],
}

# These strings often generate false positives and should lower confidence.
SAFE_GEO_PATTERNS = [
    r"\bmunicipality\b",
    r"\bcommune\b",
    r"\bcity\b",
    r"\btown\b",
    r"\bvillage\b",
    r"\bdistrict\b",
    r"\bregion\b",
    r"\bprovince\b",
    r"\bfederated state\b",
    r"\bdepartment of france\b",
    r"\boverseas department and region of france\b",
]

MILGOV_EXCLUSION_PATTERNS = [
    r"\bdepartment of france\b",
    r"\boverseas department and region of france\b",
]

CATEGORY_RULES: List[Tuple[str, str, float]] = [
    # Historical first: strongest override.
    (r"\bhistorical\b|\bformer\b|\bdefunct\b|\bextinct\b|\boccupation zone\b|\bmilitary occupation\b|\bformer country\b|\bhistorical country\b|\brepublic of soviets\b", "historical", 0.90),
    # International organizations.
    (r"\binternational organization\b|\bintergovernmental organization\b|\bunited nations\b|\bworld organization\b|\bregional organization\b", "international", 0.88),
    # Territory-level entities.
    (r"\bterritory\b|\bdependent territory\b|\boverseas territory\b|\bprotectorate\b|\bcolony\b|\boccupied territory\b", "territory", 0.84),
    # State/subdivision entities.
    (r"\bstate\b|\bprovince\b|\bdepartment\b|\bregion\b|\bcounty\b|\bcanton\b|\bfederal subject\b|\boblast\b|\bprefecture\b|\bgouvernorat\b", "state", 0.76),
    # City/municipality entities.
    (r"\bmunicipality\b|\bcity\b|\btown\b|\bvillage\b|\bcommune\b|\bborough\b|\bmunicipal part\b|\burban municipality\b|\bdistrict town\b", "city", 0.74),
]


@dataclass
class Record:
    wikidata_id: str
    name: str
    category: str
    text: str


def compile_patterns(patterns: List[str]) -> List[re.Pattern[str]]:
    return [re.compile(p, re.IGNORECASE) for p in patterns]


COMPILED_JUNK = {k: compile_patterns(v) for k, v in JUNK_PATTERNS.items()}
COMPILED_SAFE_GEO = compile_patterns(SAFE_GEO_PATTERNS)
COMPILED_MILGOV_EXCLUSIONS = compile_patterns(MILGOV_EXCLUSION_PATTERNS)
COMPILED_CATEGORY_RULES = [(re.compile(p, re.IGNORECASE), target, score) for p, target, score in CATEGORY_RULES]


def normalize_value(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, (str, int, float, bool)):
        return str(v)
    if isinstance(v, list):
        return " | ".join(normalize_value(x) for x in v)
    if isinstance(v, dict):
        chunks = []
        for k, vv in v.items():
            chunks.append(str(k))
            chunks.append(normalize_value(vv))
        return " | ".join(chunks)
    return str(v)


def parse_records(data: List[Dict[str, Any]]) -> List[Record]:
    out: List[Record] = []
    for row in data:
        if not isinstance(row, dict) or "fields" not in row:
            continue
        fields = row.get("fields", {}) or {}
        qid = fields.get("wikidata_id")
        if not qid:
            continue

        name = str(fields.get("name") or "").strip()
        category = str(fields.get("category") or "").strip().lower()
        description = fields.get("description")

        text_parts = [
            name,
            category,
            normalize_value(description),
        ]
        text = " | ".join(part for part in text_parts if part).strip()
        out.append(Record(wikidata_id=str(qid), name=name, category=category, text=text))
    return out


def junk_score(record: Record) -> Tuple[float, List[str]]:
    score = 0.0
    reasons: List[str] = []

    for label, regexes in COMPILED_JUNK.items():
        if label == "milgov" and any(rx.search(record.text) for rx in COMPILED_MILGOV_EXCLUSIONS):
            # Avoid classifying standard French administrative entities as agencies.
            continue
        hits = sum(1 for rx in regexes if rx.search(record.text))
        if hits:
            if label == "sports":
                score += min(0.55, 0.24 + hits * 0.08)
            elif label == "political":
                score += min(0.62, 0.28 + hits * 0.08)
            elif label == "company":
                score += min(0.62, 0.28 + hits * 0.08)
            elif label == "milgov":
                score += min(0.70, 0.30 + hits * 0.08)
            elif label == "ethnic_human_group":
                score += min(0.52, 0.24 + hits * 0.08)
            reasons.append(f"junk:{label}")

    # Reduce false positives for normal geo entities.
    geo_hits = sum(1 for rx in COMPILED_SAFE_GEO if rx.search(record.text))
    if geo_hits:
        score -= min(0.40, 0.08 * geo_hits)

    # Exact known false positive pattern: Czech place names with "Police".
    if record.category == "city" and record.name.lower() in {"police", "horni police", "horní police", "police nad metuji", "police nad metují"}:
        score = 0.0
        reasons = [r for r in reasons if "milgov" not in r]

    return max(0.0, min(1.0, score)), sorted(set(reasons))


def infer_category(record: Record) -> Tuple[Optional[str], float, Optional[str]]:
    # Collect all matching rules and choose the highest confidence.
    matches: List[Tuple[str, float, str]] = []
    for rx, target, score in COMPILED_CATEGORY_RULES:
        if rx.search(record.text):
            matches.append((target, score, rx.pattern))

    if not matches:
        return None, 0.0, None

    matches.sort(key=lambda x: x[1], reverse=True)
    best_target, best_score, pattern = matches[0]

    # If there are competing targets with similar confidence, mark as less certain.
    if len(matches) > 1:
        second = matches[1]
        if second[0] != best_target and (best_score - second[1]) <= 0.08:
            best_score -= 0.18

    return best_target, max(0.0, min(1.0, best_score)), pattern


def classify_record(record: Record) -> Optional[Dict[str, Any]]:
    actions: Dict[str, Any] = {}
    reasons: List[str] = []
    confidence_parts: List[float] = []

    j_score, j_reasons = junk_score(record)
    if j_score >= 0.34:
        actions["is_public"] = False
        reasons.extend(j_reasons or ["junk:rule_match"])
        confidence_parts.append(j_score)
    elif 0.22 <= j_score < 0.34:
        actions["is_verified"] = False
        reasons.append("ambiguous:junk_low_confidence")
        confidence_parts.append(j_score)

    inferred, c_score, c_pattern = infer_category(record)
    if inferred and inferred != record.category:
        if c_score >= 0.70:
            actions["category"] = inferred
            reasons.append(f"wrong_category:{record.category}->{inferred}")
            confidence_parts.append(c_score)
        else:
            actions["is_verified"] = False
            reasons.append(f"ambiguous:category_conflict:{record.category}->{inferred}")
            confidence_parts.append(c_score)

    # If there is almost no metadata to support a confident decision, keep it ambiguous.
    if not actions and len(record.text) < 28:
        actions["is_verified"] = False
        reasons.append("ambiguous:insufficient_metadata")
        confidence_parts.append(0.30)

    if not actions:
        return None

    # If an item is hidden as junk, no need to force is_verified=False too.
    if actions.get("is_public") is False and actions.get("is_verified") is False:
        del actions["is_verified"]

    confidence = sum(confidence_parts) / len(confidence_parts) if confidence_parts else 0.5
    return {
        "actions": actions,
        "reasons": sorted(set(reasons)),
        "confidence": round(confidence, 3),
        "name": record.name,
        "current_category": record.category,
    }


def build_action_map(records: List[Record]) -> Dict[str, Dict[str, Any]]:
    mapping: Dict[str, Dict[str, Any]] = {}
    for rec in records:
        decision = classify_record(rec)
        if decision:
            mapping[rec.wikidata_id] = decision
    return mapping


def save_outputs(action_map: Dict[str, Dict[str, Any]], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)

    json_path = out_dir / "action_map.json"
    with json_path.open("w", encoding="utf-8") as f:
        json.dump(action_map, f, ensure_ascii=False, indent=2, sort_keys=True)

    py_path = out_dir / "wikidata_action_map.py"
    with py_path.open("w", encoding="utf-8") as f:
        f.write("# Auto-generated by classify_flags_actions.py\n")
        f.write("# Mapping: wikidata_id -> decision payload\n\n")
        f.write("WIKIDATA_ACTION_MAP = ")
        f.write(json.dumps(action_map, ensure_ascii=False, indent=2, sort_keys=True))
        f.write("\n")

    # Summary report
    hide_count = sum(1 for v in action_map.values() if v["actions"].get("is_public") is False)
    recat_count = sum(1 for v in action_map.values() if "category" in v["actions"])
    amb_count = sum(1 for v in action_map.values() if v["actions"].get("is_verified") is False)

    summary_path = out_dir / "action_summary.txt"
    with summary_path.open("w", encoding="utf-8") as f:
        f.write(f"total_actions={len(action_map)}\n")
        f.write(f"hide_junk={hide_count}\n")
        f.write(f"category_changes={recat_count}\n")
        f.write(f"ambiguous={amb_count}\n\n")

        f.write("sample_hidden:\n")
        for qid, payload in list(sorted(action_map.items()))[:80]:
            if payload["actions"].get("is_public") is False:
                f.write(f"- {qid}: {payload['name']} | {payload['reasons']}\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Classify flags and generate wikidata_id action mapping.")
    parser.add_argument("--input", default="flags_to_clean.json", help="Path to flags_to_clean.json")
    parser.add_argument("--output-dir", default=".", help="Directory for generated outputs")
    args = parser.parse_args()

    input_path = Path(args.input)
    output_dir = Path(args.output_dir)

    with input_path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    records = parse_records(data)
    action_map = build_action_map(records)
    save_outputs(action_map, output_dir)

    hide_count = sum(1 for v in action_map.values() if v["actions"].get("is_public") is False)
    recat_count = sum(1 for v in action_map.values() if "category" in v["actions"])
    amb_count = sum(1 for v in action_map.values() if v["actions"].get("is_verified") is False)

    print(f"records={len(records)}")
    print(f"actions={len(action_map)}")
    print(f"hide_junk={hide_count}")
    print(f"category_changes={recat_count}")
    print(f"ambiguous={amb_count}")
    print(f"wrote={output_dir / 'action_map.json'}")
    print(f"wrote={output_dir / 'wikidata_action_map.py'}")
    print(f"wrote={output_dir / 'action_summary.txt'}")


if __name__ == "__main__":
    main()
