"""Asserts database/*.json is in the post-migration canonical shape (see
scripts/migrate_json.py). Fails if someone hand-edits a block back out of
shape, or a re-extraction adds a block the migration hasn't tagged."""

import json
from pathlib import Path

from scripts.migrate_json import APPLIES_BY_VALUES

_DB_DIR = Path(__file__).resolve().parent.parent / "database"
_EVENT_CATEGORIES = ("cuoi_hoi", "lam_nha", "an_tang", "xuat_hanh")


def _load(name: str) -> dict:
    return json.loads((_DB_DIR / name).read_text(encoding="utf-8"))


def _find_source_page_keys(obj, path=""):
    hits = []
    if isinstance(obj, dict):
        if "source_page" in obj:
            hits.append(path or "<root>")
        for key, value in obj.items():
            hits += _find_source_page_keys(value, f"{path}.{key}")
    elif isinstance(obj, list):
        for i, value in enumerate(obj):
            hits += _find_source_page_keys(value, f"{path}[{i}]")
    return hits


def _find_bad_source_pages(obj, path=""):
    bad = []
    if isinstance(obj, dict):
        if "source_pages" in obj:
            value = obj["source_pages"]
            if not (isinstance(value, list) and all(isinstance(p, int) for p in value)):
                bad.append((path or "<root>", value))
        for key, value in obj.items():
            bad += _find_bad_source_pages(value, f"{path}.{key}")
    elif isinstance(obj, list):
        for i, value in enumerate(obj):
            bad += _find_bad_source_pages(value, f"{path}[{i}]")
    return bad


def test_every_events_rules_block_has_applies_by():
    events_rules = _load("events_rules.json")
    for cat in _EVENT_CATEGORIES:
        for name, block in events_rules[cat].items():
            assert block.get("applies_by") in APPLIES_BY_VALUES, f"{cat}.{name}"


def test_source_pages_is_always_a_list_of_int():
    for filename in (
        "core_astrology.json",
        "events_rules.json",
        "global_bad_days.json",
        "stars_dictionary.json",
    ):
        data = _load(filename)
        assert _find_source_page_keys(data) == [], filename
        assert _find_bad_source_pages(data) == [], filename


if __name__ == "__main__":
    test_every_events_rules_block_has_applies_by()
    test_source_pages_is_always_a_list_of_int()
    print("ok")
