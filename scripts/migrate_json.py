"""One-off normalization pass over database/*.json.

Two independent transforms, both idempotent (safe to re-run):

1. source_pages: renames every `source_page` key to `source_pages`, wraps a
   bare int in a 1-element list, and parses the handful of free-text page
   RANGE strings (e.g. "58-63 (trích đoạn từ 59-60)") into a `source_pages`
   int list plus a sibling `page_note` string for the clarifying prose.

2. applies_by: tags every one of events_rules.json's ~139 event sub-rule
   blocks with what field/shape convention its data is keyed by (thang/mua/
   tuoi/nhom_tuoi/cuc/ref/status/prose/none), so a consumer doesn't have to
   guess the shape from field-name spelunking. This does NOT touch the
   underlying heterogeneous `entries` shapes -- see almanac_rules.py's module
   docstring for why a generic filter over those is a bad idea. It only adds
   a label describing the shape that's already there.

Also applies two hand-verified point fixes: one broken cross-file `ref`
pointer, and `variant_of` tags on the 4 `_v2`-suffixed duplicate/variant
blocks (whose sibling name is taken directly from each block's own `note`
text -- not a fresh judgment call, see plan).

ponytail: MANUAL_OVERRIDES below is the source of truth for the ~20-30
blocks the shape-heuristic can't classify confidently; extend it, don't
add cleverness to infer_applies_by() chasing the last few blocks. Re-run
with --dry-run after any book re-extraction to see what changed shape.
"""

import argparse
import json
import re
from pathlib import Path

DB_DIR = Path(__file__).resolve().parent.parent / "database"

APPLIES_BY_VALUES = {
    "thang", "mua", "tuoi", "nhom_tuoi", "cuc", "ref", "status", "prose", "none",
}

# event_type.block_name -> applies_by, for blocks infer_applies_by() can't
# place confidently (mixed/multi-scheme blocks, or one-off table shapes).
MANUAL_OVERRIDES: dict[str, str] = {
    "cuoi_hoi.ngay_co_than_qua_tu": "mua",  # mixed mua+thang sub-schemes, mùa is primary framing
    "cuoi_hoi.ngay_ly_sao_lia_to": "none",  # flat Can-Chi day list, no month/age keying
    "cuoi_hoi.nghinh_hon_ky_nhat": "none",
    "cuoi_hoi.chiem_nghinh_hon_cat_nhat": "none",
    "cuoi_hoi.gia_thu_bat_tuong": "tuoi",
    "cuoi_hoi.ngay_ngau_lang_chuc_nu": "mua",
    "cuoi_hoi.chu_duong_cho_viec_cuoi_vo": "none",
    "cuoi_hoi.huong_nha_nghinh_hon_theo_tuoi": "ref",
    "cuoi_hoi.khong_phong_nhat": "mua",
    "cuoi_hoi.luc_dieu_ngay_tot_di_duong": "thang",
    "cuoi_hoi.xem_ngay_nhan_duyen_sat_cong_truc_tinh_xau": "mua",
    "cuoi_hoi.thang_dai_loi_gai_ve_nha_chong": "thang",
    "cuoi_hoi.bon_mua_khong_phong": "mua",
    "cuoi_hoi.nhung_ngay_bat_luong": "prose",
    "cuoi_hoi.nhung_ngay_khong_phong_v2": "mua",
    "cuoi_hoi.chiem_nu_ve_nha_nam_loi_phuong": "prose",
    "cuoi_hoi.nhung_ngay_tam_tang_sat_hung": "prose",
    "cuoi_hoi.ngay_tieu_hong_xa": "prose",
    "cuoi_hoi.bach_ho_dai_sat_nhap_cung": "none",
    "cuoi_hoi.ngay_sat_su_bon_mua": "mua",
    "cuoi_hoi.nhung_ngay_thien_thanh_cuoi_ga_giao_dich_tot": "thang",
    "lam_nha.kim_lau": "tuoi",
    "lam_nha.duong_cong_ky_nhat_lam_nha": "ref",
    "lam_nha.ngu_hanh_tuong_sinh_khac": "ref",
    "lam_nha.nhung_ngay_thien_hoa_ky_cat_lam_nha": "prose",
    "lam_nha.nhung_ngay_thu_tru_thuong_luong": "mua",
    "lam_nha.tu_thoi_sat_su": "mua",
    "lam_nha.gio_hoang_dao": "thang",
    "lam_nha.bat_son_tuyet_mang": "prose",
    "lam_nha.bang_lap_thanh_tuoi_lam_nha": "tuoi",
    "lam_nha.huong_khoi_cong_bat_cuu_trach": "tuoi",
    "lam_nha.nhung_ngay_tao_oc_tot": "none",
    "lam_nha.tim_thang_dai_loi_trai_lam_nha_theo_menh": "thang",
    "lam_nha.nhung_ngay_thien_dao_tuong_giao": "none",
    "lam_nha.nhung_ngay_thien_hoa_ky_cat_lam_nha_v2": "thang",
    "lam_nha.chiem_sao_hoang_oc_ma_oc": "tuoi",
    "lam_nha.nhung_ngay_nguyen_ky_chi_tiet": "mua",
    "lam_nha.nhung_ngay_mua_lon_nuoi_tot": "none",
    "lam_nha.gio_quan_sat_ky_tieu_nhi_xuat_the": "prose",
    "lam_nha.bat_cuu_trach_chi_tiet_tuoi": "tuoi",
    "lam_nha.dien_tich_than_kim_lau_truyen_thuyet": "prose",
    "lam_nha.nhung_ngay_khong_nen_sua_lam_chuong_nuoi_lon": "mua",
    "lam_nha.gio_thien_la_dia_vong": "mua",
    "lam_nha.cach_tinh_ngay_truc": "prose",
    "lam_nha.nhung_ngay_thu_tu": "none",
    "lam_nha.nhung_ngay_tho_cam_kieng_dong_tho": "prose",
    "lam_nha.cuc_thong_thien_khieu": "cuc",
    "an_tang.bai_tho_tho_tu_sat_chu": "ref",
    "an_tang.sat_chu_ve_bon_mua": "ref",
    "an_tang.trung_tanh_ky_theo_gio": "status",
    "an_tang.bang_tinh_ve_viec_dam_ma": "prose",
    "an_tang.tu_thoi_trung_tang_ky_an_tang": "mua",
    "an_tang.an_tang_cat_nhat": "none",
    "an_tang.phep_xem_12_thang_hoang_long": "thang",
    "an_tang.cach_tru_trung": "prose",
    "an_tang.bang_tinh_ve_viec_dam_ma_grid": "none",
    "an_tang.nhung_ngay_ky_tham_nguoi_om": "prose",
    "an_tang.nhung_ngay_tu_ly": "prose",
    "an_tang.nhung_ngay_tu_tuyet": "prose",
    "xuat_hanh.chu_cong_xuat_hanh": "none",
    "xuat_hanh.bang_tinh_ngay_gio_tot_di_duong_viec_nho": "status",
    "xuat_hanh.gio_hoang_dao_hac_dao": "status",
    "xuat_hanh.luc_dieu_ngay_gio_tot_di_duong": "thang",
    "xuat_hanh.nhung_ngay_khong_vong_bon_mua": "mua",
    "xuat_hanh.luc_nham_dai_don": "thang",
    "cuoi_hoi.hong_sa_ky_nhat": "mua",
    "cuoi_hoi.tre_con_hay_khoc_da_de": "thang",
    "cuoi_hoi.tre_con_kho_nuoi_tho_rang": "thang",
    "cuoi_hoi.khong_phong_toi_ky_gio": "none",
    "cuoi_hoi.gia_thu_khong_phong_ky_nhat": "thang",
    "cuoi_hoi.thien_dia_tranh_hung_gia_thu_ky_nhat": "thang",
    "cuoi_hoi.ngay_bat_ma_sat_ky_hop_hon": "thang",
    "cuoi_hoi.gia_thu_dai_hoa_tai_vong_nhat": "thang",
    "cuoi_hoi.tu_thoi_hoang_tuyen_bat_ma_ky_gia_thu": "mua",
    "cuoi_hoi.thai_bach_chu_thuong_ky_nghinh_hon": "none",
    "cuoi_hoi.thien_cau_hanh_thuc_gia_thu_tu_thoi_dai_hung": "mua",
    "cuoi_hoi.ngay_nu_that_khong_phong": "thang",
    "cuoi_hoi.that_ac_dai_bai_bach_su_ky": "none",
    "cuoi_hoi.chiem_sao_quy_khoc_tinh": "thang",
    "cuoi_hoi.chiem_ngu_mo_bach_su_ky": "thang",
    "cuoi_hoi.chiem_kim_than_that_sat_ky_phap": "none",
    "cuoi_hoi.nhung_ngay_pha_quan_ky_gia_thu": "none",
    "cuoi_hoi.nhung_ngay_nghinh_hon_hop": "none",
    "lam_nha.gio_thu_tu_ky": "thang",
    "lam_nha.nhung_ngay_thien_ma_ky_gia_thu_va_tao_oc": "mua",
    "lam_nha.nhung_ngay_trung_nhi_ky": "none",
    "lam_nha.nhung_ngay_lo_ban_sat_ky_phat_moc": "mua",
    "lam_nha.ky_khoi_cong_lam_nha_phu_dau_sat": "mua",
    "lam_nha.nhung_ngay_ky_lam_nha_lon": "none",
    "lam_nha.nhap_trach_cu_cat_nhat": "none",
    "lam_nha.ngay_truc": "none",
    "lam_nha.cach_tim_sao_thien_y_dong_giuong": "prose",
    "an_tang.phep_tinh_gio": "none",
    "xuat_hanh.chiem_vang_vong_nhat": "thang",
    "xuat_hanh.nhung_ngay_xich_tong_tu_giang_ha": "thang",
    "xuat_hanh.chiem_thien_loi_da_gio": "none",
    "xuat_hanh.ngay_gio_dinh_cuc": "none",
}

VARIANT_OF: dict[str, tuple[str, str]] = {
    # key -> (sibling_key, one-line relationship note, taken from the
    # block's own existing `note` text -- see plan step 4)
    "cuoi_hoi.ngay_co_than_qua_tu_theo_thang_v2": (
        "ngay_co_than_qua_tu",
        "Hệ Cô Thần Quả Tú khác, theo tháng trực tiếp; có thể trùng hoặc là dị bản của ngay_co_than_qua_tu.",
    ),
    "cuoi_hoi.nhung_ngay_khong_phong_v2": (
        "bon_mua_khong_phong",
        "Một hệ Không Phòng khác (theo mùa), khác bon_mua_khong_phong.",
    ),
    "lam_nha.nhung_ngay_thien_hoa_ky_cat_lam_nha_v2": (
        "nhung_ngay_thien_hoa_ky_cat_lam_nha",
        "Ngày Thiên Hỏa kỵ cất làm nhà theo nhóm tháng dạng con vật; khác bản thơ ở nhung_ngay_thien_hoa_ky_cat_lam_nha.",
    ),
    "an_tang.nhung_ngay_thien_hy_an_tang_v2": (
        "nhung_ngay_thien_hy_an_tang",
        "Bảng Thiên Hỷ An Táng theo tháng riêng (trang 150); đối chiếu với nhung_ngay_thien_hy_an_tang.",
    ),
}

REF_FIXES: dict[str, str] = {
    "cuoi_hoi.huong_nha_nghinh_hon_theo_tuoi": "xem events_rules.json -> lam_nha.huong_nha_ky_theo_tuoi",
}

_SEASON_KEYS = {"xuan", "ha", "thu", "dong"}
_QUARTER_PREFIXES = ("tu_manh", "tu_trong", "tu_quy")


def _first_entry(block: dict) -> dict | None:
    for key in ("entries",):
        val = block.get(key)
        if isinstance(val, list) and val and isinstance(val[0], dict):
            return val[0]
    theo_thang = block.get("theo_thang")
    if isinstance(theo_thang, list) and theo_thang and isinstance(theo_thang[0], dict):
        return theo_thang[0]
    if isinstance(theo_thang, dict):
        inner = theo_thang.get("entries")
        if isinstance(inner, list) and inner and isinstance(inner[0], dict):
            return inner[0]
    return None


def infer_applies_by(qualified_name: str, block: dict) -> str | None:
    """Mechanical shape checks. Returns None if no rule fires (caller falls
    back to MANUAL_OVERRIDES)."""
    if qualified_name in MANUAL_OVERRIDES:
        return MANUAL_OVERRIDES[qualified_name]

    keys = set(block.keys())
    non_meta = keys - {"note", "source_page", "source_pages", "page_note"}

    if non_meta == {"ref"} or "ref" in keys and not non_meta - {"ref"}:
        return "ref"
    if non_meta == {"status"}:
        return "status"
    if "cac_cuc" in keys:
        return "cuc"

    entry = _first_entry(block)
    if entry and "nhom_tuoi" in entry:
        return "nhom_tuoi"
    if any(k.startswith(_QUARTER_PREFIXES) for k in keys):
        return "mua"
    if _SEASON_KEYS & keys:
        return "mua"
    if "theo_thang" in keys:
        return "thang"
    if entry and "thang" in entry:
        return "thang"
    if entry and "tuoi" in entry:
        return "tuoi"
    if not non_meta:
        return "none"
    if non_meta & {"tho", "giai", "giai_nghia"} and not (entry or _SEASON_KEYS & keys):
        return "prose"

    return None


def normalize_source_pages(obj):
    """Recursively rename source_page -> source_pages (always list[int]),
    parsing free-text page-range strings into ints + a page_note."""
    if isinstance(obj, dict):
        if "source_page" in obj:
            obj["source_pages"] = obj.pop("source_page")
        if "source_pages" in obj:
            val = obj["source_pages"]
            if isinstance(val, int):
                obj["source_pages"] = [val]
            elif isinstance(val, str):
                range_match = re.match(r"^\s*(\d+)(?:\s*-\s*(\d+))?", val)
                if range_match:
                    start = int(range_match.group(1))
                    end = int(range_match.group(2)) if range_match.group(2) else start
                    pages = list(range(start, end + 1))
                    prose = val[range_match.end():].strip(" ()")
                else:
                    pages = [int(n) for n in re.findall(r"\d+", val)]
                    prose = ""
                obj["source_pages"] = pages
                if prose:
                    obj["page_note"] = prose
        for v in obj.values():
            normalize_source_pages(v)
    elif isinstance(obj, list):
        for v in obj:
            normalize_source_pages(v)


def migrate_events_rules(data: dict, report: list[str]) -> None:
    for cat in ("cuoi_hoi", "lam_nha", "an_tang", "xuat_hanh"):
        for name, block in data[cat].items():
            qualified = f"{cat}.{name}"
            applies_by = infer_applies_by(qualified, block)
            if applies_by is None:
                report.append(qualified)
                continue
            block["applies_by"] = applies_by

        for name, ref_text in REF_FIXES.items():
            if name.startswith(f"{cat}."):
                data[cat][name.split(".", 1)[1]]["ref"] = ref_text

        for name, (sibling, note) in VARIANT_OF.items():
            if name.startswith(f"{cat}."):
                block_name = name.split(".", 1)[1]
                data[cat][block_name]["variant_of"] = sibling
                data[cat][block_name]["variant_note"] = note


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    files = {
        name: json.loads((DB_DIR / name).read_text(encoding="utf-8"))
        for name in (
            "core_astrology.json",
            "events_rules.json",
            "global_bad_days.json",
            "stars_dictionary.json",
        )
    }

    report: list[str] = []
    migrate_events_rules(files["events_rules.json"], report)
    for data in files.values():
        normalize_source_pages(data)

    if report:
        print(f"{len(report)} block(s) need a MANUAL_OVERRIDES entry:")
        for name in report:
            print(f"  {name}")
    else:
        print("All events_rules.json blocks classified.")

    if args.dry_run:
        print("\n--dry-run: no files written.")
        return

    for name, data in files.items():
        (DB_DIR / name).write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    print(f"\nWrote {len(files)} file(s) to {DB_DIR}")


if __name__ == "__main__":
    main()
