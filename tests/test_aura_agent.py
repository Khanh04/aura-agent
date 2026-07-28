from pydantic_ai import ModelRetry

from app.agent.aura_agent import get_candidate_days
from app.services import almanac_rules


def test_get_candidate_days_length_and_flags_consistency():
    days = get_candidate_days("2026-07-01", "2026-07-10")
    assert len(days) == 10
    assert days[0]["gregorian_date"] == "2026-07-01"
    assert days[-1]["gregorian_date"] == "2026-07-10"
    for d in days:
        assert d["bad_day_flags"] == almanac_rules.get_global_bad_day_flags(d["lunar_day"], d["lunar_month"])


def test_get_candidate_days_rejects_over_cap():
    try:
        get_candidate_days("2026-01-01", "2026-06-01")  # >60 days
        assert False, "expected ModelRetry"
    except ModelRetry:
        pass


if __name__ == "__main__":
    test_get_candidate_days_length_and_flags_consistency()
    test_get_candidate_days_rejects_over_cap()
    print("ok")
