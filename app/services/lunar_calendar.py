"""Gregorian <-> Vietnamese lunar date conversion.

Conversion math (jdn/jdn2date/get_new_moon_day/get_sun_longitude_aa/
get_lunar_month_11/get_leap_month_offset/solar_to_lunar) is adapted from the
`vnlunar` PyPI package (MIT), itself based on Ho Ngoc Duc's astronomical
algorithm for the Vietnamese lunar calendar. Vendored here (not a runtime
dependency) since it's a small, stable, rarely-changing algorithm and
`vnlunar` is an unmaintained single-author "beta" package.

ponytail: time_zone is fixed at 7.0 (modern Vietnam/UTC+7). Vietnam used
UTC+8 (Beijing time) before 1967, so dates before ~1967 can occasionally get
the wrong leap-month placement near month boundaries. Fine for the app's
supported 1900-2100 range; add the historical timezone switch if pre-1967
accuracy is ever needed.
"""

import math
from datetime import date, timedelta
from functools import lru_cache
from typing import TypedDict

from app.services import almanac_rules

_TIME_ZONE = 7.0

# Universal Can (Heavenly Stem) / Chi (Earthly Branch) names -- fixed
# constants of the calendar system itself, not almanac-specific data, so
# they're safe to hardcode (unlike menh/nap_am, which come from
# core_astrology.json so the app's wording always matches the source book).
_CAN = ["Giáp", "Ất", "Bính", "Đinh", "Mậu", "Kỷ", "Canh", "Tân", "Nhâm", "Quý"]
_CHI = ["Tý", "Sửu", "Dần", "Mão", "Thìn", "Tỵ", "Ngọ", "Mùi", "Thân", "Dậu", "Tuất", "Hợi"]


class LunarDate(TypedDict):
    day: int
    month: int
    year: int
    is_leap_month: bool
    jd: int


def _INT(d: float) -> int:
    return math.floor(d)


def jdn(dd: int, mm: int, yy: int) -> int:
    a = _INT((14 - mm) / 12)
    y = yy + 4800 - a
    m = mm + 12 * a - 3
    return dd + _INT((153 * m + 2) / 5) + 365 * y + _INT(y / 4) - _INT(y / 100) + _INT(y / 400) - 32045


def jdn2date(jd: int) -> tuple[int, int, int]:
    if jd < 2299161:
        a = jd
    else:
        alpha = _INT((jd - 1867216.25) / 36524.25)
        a = jd + 1 + alpha - _INT(alpha / 4)
    b = a + 1524
    c = _INT((b - 122.1) / 365.25)
    d = _INT(365.25 * c)
    e = _INT((b - d) / 30.6001)
    dd = _INT(b - d - _INT(30.6001 * e))
    mm = e - 1 if e < 14 else e - 13
    yyyy = c - 4715 if mm < 3 else c - 4716
    return (dd, mm, yyyy)


def _get_new_moon_day(k: float) -> int:
    t = k / 1236.85
    t2 = t * t
    t3 = t2 * t
    dr = math.pi / 180

    jd1 = 2415020.75933 + 29.53058868 * k + 0.0001178 * t2 - 0.000000155 * t3
    jd1 += 0.00033 * math.sin((166.56 + 132.87 * t - 0.009173 * t2) * dr)

    m = 359.2242 + 29.10535608 * k - 0.0000333 * t2 - 0.00000347 * t3
    mpr = 306.0253 + 385.81691806 * k + 0.0107306 * t2 + 0.00001236 * t3
    f = 21.2964 + 390.67050646 * k - 0.0016528 * t2 - 0.00000239 * t3

    c1 = (0.1734 - 0.000393 * t) * math.sin(m * dr) + 0.0021 * math.sin(2 * dr * m)
    c1 -= 0.4068 * math.sin(mpr * dr) - 0.0161 * math.sin(dr * 2 * mpr)
    c1 -= 0.0004 * math.sin(dr * 3 * mpr)
    c1 += 0.0104 * math.sin(dr * 2 * f) - 0.0051 * math.sin(dr * (m + mpr))
    c1 -= 0.0074 * math.sin(dr * (m - mpr)) - 0.0004 * math.sin(dr * (2 * f + m))
    c1 -= 0.0004 * math.sin(dr * (2 * f - m)) + 0.0006 * math.sin(dr * (2 * f + mpr))
    c1 += 0.0010 * math.sin(dr * (2 * f - mpr)) + 0.0005 * math.sin(dr * (2 * mpr + m))

    if t < -11:
        deltat = 0.001 + 0.000839 * t + 0.0002261 * t2 - 0.00000845 * t3 - 0.000000081 * t * t3
    else:
        deltat = -0.000278 + 0.000265 * t + 0.000262 * t2

    jd_new = jd1 + c1 - deltat
    return _INT(jd_new + 0.5 + _TIME_ZONE / 24)


def _get_sun_longitude_deg(jd: int) -> float:
    t = (jd - 2451545.5 - _TIME_ZONE / 24) / 36525
    t2 = t * t
    dr = math.pi / 180

    m = 357.52910 + 35999.05030 * t - 0.0001559 * t2 - 0.00000048 * t * t2
    l0 = 280.46645 + 36000.76983 * t + 0.0003032 * t2

    dl = (1.914600 - 0.004817 * t - 0.000014 * t2) * math.sin(dr * m)
    dl += (0.019993 - 0.000101 * t) * math.sin(dr * 2 * m) + 0.000290 * math.sin(dr * 3 * m)

    l = l0 + dl
    return l - 360 * _INT(l / 360)


def _get_sun_longitude_sector(jd: int) -> int:
    return _INT(_get_sun_longitude_deg(jd) / 30)


def get_tiet_khi_index(jd: int) -> int:
    """Which of the 12 major tiet-khi (solar terms starting at Lap Xuan) jd
    falls in, as index 0-11 in the same order as events_rules.json's
    cach_tinh_ngay_truc.diem_khoi_truc_kien_theo_tiet_khi list. Tiet-khi
    boundaries sit at 315, 345, 15, 45... degrees -- a 15-degree phase offset
    from the trung-khi sectors _get_sun_longitude_sector uses for lunar-month
    math, using the same underlying sun-longitude formula.

    ponytail: like the rest of this module, resolves to whole-day (jd)
    granularity, not the exact crossing instant -- transitions land about a
    day later than commonly-published tiet-khi dates (verified against 2024:
    e.g. Lap Xuan and Mang Chung both flip a day after their usual cited
    date). Same class of imprecision as the leap-month boundary caveat above;
    not fixed for the same reason (small, stable algorithm; day-level
    precision is enough for this app)."""
    return _INT(((_get_sun_longitude_deg(jd) - 315) % 360) / 30)


def _get_lunar_month_11(yy: int) -> int:
    off = jdn(31, 12, yy) - 2415021
    k = _INT(off / 29.530588853)
    nm = _get_new_moon_day(k)
    if _get_sun_longitude_sector(nm) >= 9:
        nm = _get_new_moon_day(k - 1)
    return nm


def _get_leap_month_offset(a11: int) -> int:
    k = _INT((a11 - 2415021.076998695) / 29.530588853 + 0.5)
    last = 0
    i = 1
    arc = _get_sun_longitude_sector(_get_new_moon_day(k + i))
    while arc != last and i < 14:
        last = arc
        i += 1
        arc = _get_sun_longitude_sector(_get_new_moon_day(k + i))
    return i - 1


def solar_to_lunar(day: int, month: int, year: int) -> LunarDate:
    """Convert a Gregorian date to its Vietnamese lunar equivalent."""
    day_number = jdn(day, month, year)
    k = _INT((day_number - 2415021.076998695) / 29.530588853)
    month_start = _get_new_moon_day(k + 1)
    if month_start > day_number:
        month_start = _get_new_moon_day(k)

    a11 = _get_lunar_month_11(year)
    b11 = a11
    if a11 >= month_start:
        lunar_year = year
        a11 = _get_lunar_month_11(year - 1)
    else:
        lunar_year = year + 1
        b11 = _get_lunar_month_11(year + 1)

    lunar_day = day_number - month_start + 1
    diff = _INT((month_start - a11) / 29)
    is_leap_month = False
    lunar_month = diff + 11

    if b11 - a11 > 365:
        leap_month_diff = _get_leap_month_offset(a11)
        if diff >= leap_month_diff:
            lunar_month = diff + 10
            if diff == leap_month_diff:
                is_leap_month = True

    if lunar_month > 12:
        lunar_month -= 12
    if lunar_month >= 11 and diff < 4:
        lunar_year -= 1

    return LunarDate(day=lunar_day, month=lunar_month, year=lunar_year, is_leap_month=is_leap_month, jd=day_number)


_MAX_RANGE_DAYS = 60  # ~2 lunar months; same brute-force-window size lunar_to_solar already uses.


def solar_range_to_lunar(start: date, end: date) -> list[LunarDate]:
    """Convert every day in [start, end] (inclusive) to its lunar equivalent.
    Loops solar_to_lunar per day -- fine at this capped size. Raises ValueError
    if the range is empty/backwards or exceeds the cap; callers must narrow."""
    days = (end - start).days + 1
    if days <= 0:
        raise ValueError("end date must not be before start date")
    if days > _MAX_RANGE_DAYS:
        raise ValueError(
            f"range spans {days} days, over the {_MAX_RANGE_DAYS}-day cap -- do not retry with a "
            "smaller range yourself; tell the user the range is too wide and ask them to narrow it"
        )
    return [
        solar_to_lunar((start + timedelta(n)).day, (start + timedelta(n)).month, (start + timedelta(n)).year)
        for n in range(days)
    ]


def lunar_to_solar(day: int, month: int, year: int, is_leap_month: bool = False) -> date:
    """Inverse of solar_to_lunar. Brute-force search over a window around the
    target lunar date -- simplest correct approach; this isn't called in any
    hot path, so there's no reason to derive the closed-form inverse."""
    guess = date(year, 1, 1) + timedelta(days=(month - 1) * 29 + day - 1)
    for offset in range(-60, 61):
        candidate = guess + timedelta(days=offset)
        lunar = solar_to_lunar(candidate.day, candidate.month, candidate.year)
        if (
            lunar["day"] == day
            and lunar["month"] == month
            and lunar["year"] == year
            and lunar["is_leap_month"] == is_leap_month
        ):
            return candidate
    raise ValueError(f"no solar date found for lunar {day}/{month}/{year} (leap={is_leap_month})")


def get_can_chi_for_day(jd: int) -> str:
    return f"{_CAN[(jd + 9) % 10]} {_CHI[(jd + 1) % 12]}"


def get_can_chi_for_month(lunar_month: int, lunar_year: int) -> str:
    return f"{_CAN[(lunar_year * 12 + lunar_month + 3) % 10]} {_CHI[(lunar_month + 1) % 12]}"


@lru_cache(maxsize=128)
def get_can_chi_for_year(year: int) -> dict:
    """Year Can-Chi + menh/nap_am, resolved from core_astrology.json's
    luc_thap_hoa_giap table (not hardcoded) so wording matches the almanac."""
    n = (year - 4) % 60
    entry_index, member = divmod(n, 2)
    entry = almanac_rules.get_luc_thap_hoa_giap_entry(entry_index)
    return {
        "can_chi": entry["can_chi_pair"][member],
        "menh": entry["menh"],
        "nap_am": entry["nap_am"],
    }
