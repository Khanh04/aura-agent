from app.services import lunar_calendar


def test_tet_2024():
    lunar = lunar_calendar.solar_to_lunar(10, 2, 2024)
    assert (lunar["day"], lunar["month"], lunar["year"], lunar["is_leap_month"]) == (1, 1, 2024, False)


def test_tet_2025():
    lunar = lunar_calendar.solar_to_lunar(29, 1, 2025)
    assert (lunar["day"], lunar["month"], lunar["year"], lunar["is_leap_month"]) == (1, 1, 2025, False)


def test_ordinary_date():
    # 2026-07-28 (today, per the session's system date) -> lunar 15/6/2026 (rằm tháng 6).
    lunar = lunar_calendar.solar_to_lunar(28, 7, 2026)
    assert (lunar["day"], lunar["month"], lunar["year"], lunar["is_leap_month"]) == (15, 6, 2026, False)


def test_round_trip():
    for d, m, y in [(10, 2, 2024), (29, 1, 2025), (28, 7, 2026), (1, 1, 2000), (31, 12, 2099)]:
        lunar = lunar_calendar.solar_to_lunar(d, m, y)
        solar = lunar_calendar.lunar_to_solar(lunar["day"], lunar["month"], lunar["year"], lunar["is_leap_month"])
        assert (solar.day, solar.month, solar.year) == (d, m, y)


def test_can_chi_for_year_matches_almanac():
    profile = lunar_calendar.get_can_chi_for_year(1984)
    assert profile["can_chi"] == "Giáp Tý"
    assert profile["menh"] == "Kim"
    assert profile["nap_am"] == "Vàng dưới biển"

    profile_next = lunar_calendar.get_can_chi_for_year(1985)
    assert profile_next["can_chi"] == "Ất Sửu"
    assert profile_next["menh"] == "Kim"


def test_can_chi_for_day_and_month_are_valid_names():
    jd = lunar_calendar.jdn(28, 7, 2026)
    day_can_chi = lunar_calendar.get_can_chi_for_day(jd)
    can, chi = day_can_chi.split()
    assert can in lunar_calendar._CAN
    assert chi in lunar_calendar._CHI

    month_can_chi = lunar_calendar.get_can_chi_for_month(6, 2026)
    can, chi = month_can_chi.split()
    assert can in lunar_calendar._CAN
    assert chi in lunar_calendar._CHI


if __name__ == "__main__":
    test_tet_2024()
    test_tet_2025()
    test_ordinary_date()
    test_round_trip()
    test_can_chi_for_year_matches_almanac()
    test_can_chi_for_day_and_month_are_valid_names()
    print("ok")
