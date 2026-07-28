"""Plain functions querying the almanac JSON in database/*.json.

Each function is one filter over one already-loaded dict -- no repository or
query-builder abstraction, mirroring argus-agent's db.py (plain functions
over sqlite3.Row).

ponytail: events_rules.json's per-event blocks (cuoi_hoi/lam_nha/an_tang/
xuat_hanh) use inconsistent field names across sub-rules (some keyed by
"thang", some by "mua"/season, some by "tuoi"/age, some by nothing at all --
see cuoi_hoi's 45 differently-shaped sub-rules). Writing a generic filter
over that would silently drop rules that don't match its assumptions, which
is worse than returning too much. get_event_rules returns the whole
category block and lets the agent (which already has the resolved lunar
month/day Can-Chi in conversation context) pick out what's relevant and
cite the source_pages -- consistent with this app's overall design: raw data
in, LLM synthesis out.
"""

import json
from functools import lru_cache
from pathlib import Path
from typing import Literal

_DB_DIR = Path(__file__).resolve().parent.parent.parent / "database"

_SEASON_BY_MONTH = {
    1: "Xuân", 2: "Xuân", 3: "Xuân",
    4: "Hạ", 5: "Hạ", 6: "Hạ",
    7: "Thu", 8: "Thu", 9: "Thu",
    10: "Đông", 11: "Đông", 12: "Đông",
}

EventType = Literal["cuoi_hoi", "lam_nha", "an_tang", "xuat_hanh"]


@lru_cache(maxsize=1)
def _core_astrology() -> dict:
    return json.loads((_DB_DIR / "core_astrology.json").read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def _events_rules() -> dict:
    return json.loads((_DB_DIR / "events_rules.json").read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def _global_bad_days() -> dict:
    return json.loads((_DB_DIR / "global_bad_days.json").read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def _stars_dictionary() -> dict:
    return json.loads((_DB_DIR / "stars_dictionary.json").read_text(encoding="utf-8"))


def get_luc_thap_hoa_giap_entry(entry_index: int) -> dict:
    """0-based index into the 30-entry, 2-year-pair sexagenary cycle table."""
    return _core_astrology()["luc_thap_hoa_giap"][entry_index]


def get_year_profile(can_chi_year: str) -> dict:
    """Menh/nap_am (via the sexagenary table) + directional luck + Tam Tai
    Han exposure for a year, identified by its Can-Chi string (e.g. "Giáp Tý")."""
    chi = can_chi_year.split()[-1]
    core = _core_astrology()

    cycle_entry = next((e for e in core["luc_thap_hoa_giap"] if can_chi_year in e["can_chi_pair"]), None)
    direction = next((e for e in core["phuong_huong_tot_tung_nam"]["entries"] if chi in e["nam_nhom"]), None)
    tam_tai = next((e for e in core["tam_tai_han"]["bang_tra"] if chi in e["nhom_sinh"]), None)

    return {
        "can_chi": can_chi_year,
        "menh": cycle_entry["menh"] if cycle_entry else None,
        "nap_am": cycle_entry["nap_am"] if cycle_entry else None,
        "phuong_huong_tot_tung_nam": direction,
        "tam_tai_han": tam_tai,
    }


def get_global_bad_day_flags(lunar_day: int, lunar_month: int | None = None) -> list[dict]:
    """Universal bad-day rules. Tam Nương/Nguyệt Kỵ repeat every month
    (day-of-month only); Dương Công's 13 days are month-specific, so it's
    only checked when lunar_month is given."""
    data = _global_bad_days()
    flags = []

    for key in ("tam_nuong", "nguyet_ky"):
        block = data[key]
        if lunar_day in block["ngay_am_lich"]:
            flags.append({"rule": key, "note": block["note"], "source_pages": block["source_pages"]})

    if lunar_month is not None:
        dc = data["duong_cong_ky_nhat"]
        month_entry = next((m for m in dc["theo_thang"] if m["thang"] == lunar_month), None)
        if month_entry and lunar_day in month_entry["ngay_am_lich"]:
            flags.append({"rule": "duong_cong_ky_nhat", "note": dc["note"], "source_pages": dc["source_pages"]})

    return flags


def get_event_rules(event_type: EventType) -> dict:
    """Whole rule set for one of the 4 curated event categories -- see
    module docstring for why this isn't filtered further here."""
    return _events_rules()[event_type]


def get_star_info(day_chi: str, lunar_month: int) -> dict:
    """Stars/officers for a given day-branch, looked up both by month and
    by season (the book keeps two independently-compiled tables)."""
    data = _stars_dictionary()
    season = _SEASON_BY_MONTH[lunar_month]

    monthly = data["monthly_day_branch_stars"]["months"].get(str(lunar_month), {}).get("chi", {}).get(day_chi, [])
    seasonal = data["seasonal_day_branch_stars"]["seasons"].get(season, {}).get("chi", {}).get(day_chi, [])

    return {
        "day_chi": day_chi,
        "lunar_month": lunar_month,
        "season": season,
        "monthly_stars": monthly,
        "seasonal_stars": seasonal,
    }


def get_kim_lau(birth_year: int, target_lunar_year: int) -> dict:
    """Kim Lâu: bad luck for cưới hỏi/làm nhà if tuổi mụ's last digit is in
    {1,3,6,8}. The book's own prose note says "mod 9", but its own worked
    examples (vi_du_tuoi_pham: 21,23,26,28) only satisfy a mod-10 (last
    digit) rule, not mod 9 -- e.g. 23 % 9 == 5, not in {1,3,6,8}, while
    23 % 10 == 3, which is. Trusting the concrete examples over the
    (apparently mistranscribed) prose gloss."""
    block = _events_rules()["lam_nha"]["kim_lau"]
    tuoi_mu = target_lunar_year - birth_year + 1
    remainder = tuoi_mu % 10
    return {
        "tuoi_mu": tuoi_mu,
        "remainder_mod_10": remainder,
        "is_kim_lau": remainder in (1, 3, 6, 8),
        "note": block["note"],
        "cau_ca": block["cau_ca"],
        "source_pages": block["source_pages"],
    }


def get_cuc_thong_thien_khieu(birth_can_chi: str, age: int) -> dict:
    """18-cục cycle (Xem Tuổi Làm Nhà, Dựng Vợ, Gả Chồng): each cục spans 10
    years starting from the person's birth Can-Chi cục, wrapping after 18.

    ponytail: this follows the block's explicit cach_tinh prose ("mỗi cục
    ứng 10 tuổi"). Its own worked example (vi_du) is garbled OCR and actually
    contradicts that same prose (it shows 3 different cục for 3 consecutive
    ages within one decade, which a 10-year-per-cục rule can't produce) --
    the file elsewhere admits OCR quality issues in nearby tables. Trusting
    the clearly-stated rule over the damaged example; flag this as lower
    confidence in the agent's response rather than tuning the code to match
    an unreadable example.
    """
    block = _events_rules()["lam_nha"]["cuc_thong_thien_khieu"]
    cuc_list = block["cac_cuc"]

    start_cuc = next((c["cuc"] for c in cuc_list if birth_can_chi in c["tuoi"]), None)
    if start_cuc is None:
        return {"available": False, "reason": f"birth Can-Chi '{birth_can_chi}' not found in the 18-cục table"}

    # Cục 1 = ages 1-10, cục 2 = ages 11-20, ... wrapping back to cục 1 after 18.
    steps = (age - 1) // 10
    current_cuc_number = ((start_cuc - 1 + steps) % 18) + 1
    entry = next(c for c in cuc_list if c["cuc"] == current_cuc_number)

    return {
        "available": True,
        "birth_can_chi": birth_can_chi,
        "age": age,
        "cuc": entry["cuc"],
        "ten": entry["ten"],
        "y_nghia": entry["y_nghia"],
        "tot_xau": entry["tot_xau"],
        "source_pages": block["source_pages"],
    }


def get_trung_tang(birth_year: int, death_lunar_year: int, gender: Literal["nam", "nu"]) -> dict:
    """Trùng Tang: age-at-death counted around a 12-cung table, direction
    depends on the deceased's gender."""
    block = _events_rules()["an_tang"]["bang_tinh_ve_viec_dam_ma_grid"]
    age_at_death = death_lunar_year - birth_year + 1

    # nam: start at cung Dần (index 2 in the 12-Chi cycle), counting backward;
    # nu: start at cung Thân (index 8), counting forward. Age 1 = start cung.
    chi_order = ["Tý", "Sửu", "Dần", "Mão", "Thìn", "Tỵ", "Ngọ", "Mùi", "Thân", "Dậu", "Tuất", "Hợi"]
    if gender == "nam":
        start_index, step = chi_order.index("Dần"), -1
    else:
        start_index, step = chi_order.index("Thân"), 1
    landing_chi = chi_order[(start_index + step * (age_at_death - 1)) % 12]

    if landing_chi in block["thien_di"]:
        zone = "thien_di"
    elif landing_chi in block["nhap_mo"]:
        zone = "nhap_mo"
    else:
        zone = "trung_tang"

    return {
        "age_at_death": age_at_death,
        "landing_chi": landing_chi,
        "zone": zone,
        "note": block["note"],
        "source_pages": block["source_pages"],
    }
