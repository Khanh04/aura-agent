from app.services import almanac_rules as ar


def test_tam_nuong_day():
    flags = ar.get_global_bad_day_flags(3)
    assert any(f["rule"] == "tam_nuong" for f in flags)


def test_non_bad_day_has_no_flags():
    # Day 2 isn't in tam_nuong (3,7,13,18,22,27) or nguyet_ky (5,14,23).
    flags = ar.get_global_bad_day_flags(2)
    assert flags == []


def test_duong_cong_ky_nhat_is_month_specific():
    # Month 1's Duong Cong day is 13 (per database/global_bad_days.json).
    assert any(f["rule"] == "duong_cong_ky_nhat" for f in ar.get_global_bad_day_flags(13, lunar_month=1))
    assert not any(f["rule"] == "duong_cong_ky_nhat" for f in ar.get_global_bad_day_flags(13, lunar_month=2))


def test_kim_lau_matches_book_examples():
    # database/events_rules.json lam_nha.kim_lau.vi_du_tuoi_pham: [21, 23, 26, 28].
    # tuoi_mu = target_lunar_year - birth_year + 1; use target year = birth_year + age - 1.
    for age in (21, 23, 26, 28):
        result = ar.get_kim_lau(birth_year=2000, target_lunar_year=2000 + age - 1)
        assert result["tuoi_mu"] == age
        assert result["is_kim_lau"] is True

    # A non-Kim-Lau age (last digit not in {1,3,6,8}), e.g. 22.
    result = ar.get_kim_lau(birth_year=2000, target_lunar_year=2000 + 22 - 1)
    assert result["is_kim_lau"] is False


def test_kim_lau_unavailable_without_birth_year():
    assert ar.get_kim_lau(birth_year=None, target_lunar_year=2026) == {
        "available": False,
        "reason": "birth_year not provided",
    }


def test_cuc_thong_thien_khieu_birth_cuc_lookup():
    # database/events_rules.json lam_nha.cuc_thong_thien_khieu.cac_cuc: cục 1's
    # "tuoi" list is ["Giáp Tý", "Canh Tuất", "Tân Mão"].
    result = ar.get_cuc_thong_thien_khieu("Tân Mão", age=1)
    assert result["available"] is True
    assert result["cuc"] == 1

    # Ages 1-10 stay in the birth cục; age 11 steps to the next one.
    assert ar.get_cuc_thong_thien_khieu("Tân Mão", age=10)["cuc"] == 1
    assert ar.get_cuc_thong_thien_khieu("Tân Mão", age=11)["cuc"] == 2


def test_cuc_thong_thien_khieu_wraps_after_18():
    start = ar.get_cuc_thong_thien_khieu("Tân Mão", age=1)["cuc"]
    wrapped = ar.get_cuc_thong_thien_khieu("Tân Mão", age=1 + 18 * 10)
    assert wrapped["cuc"] == start


def test_cuc_thong_thien_khieu_unavailable_without_age():
    assert ar.get_cuc_thong_thien_khieu("Tân Mão", age=None) == {
        "available": False,
        "reason": "age not provided",
    }


def test_trung_tang_gender_changes_direction():
    nam = ar.get_trung_tang(birth_year=2000, death_lunar_year=2026, gender="nam")
    nu = ar.get_trung_tang(birth_year=2000, death_lunar_year=2026, gender="nu")
    assert nam["landing_chi"] != nu["landing_chi"]
    assert nam["zone"] in ("thien_di", "nhap_mo", "trung_tang")
    assert nu["zone"] in ("thien_di", "nhap_mo", "trung_tang")
    assert isinstance(nam["source_pages"], list) and all(isinstance(p, int) for p in nam["source_pages"])


def test_trung_tang_unavailable_without_birth_year():
    assert ar.get_trung_tang(birth_year=None, death_lunar_year=2026, gender="nam") == {
        "available": False,
        "reason": "birth_year not provided",
    }


def test_get_year_profile_returns_menh_and_direction():
    profile = ar.get_year_profile("Giáp Tý")
    assert profile["menh"] == "Kim"
    assert profile["nap_am"] == "Vàng dưới biển"


def test_get_event_rules_returns_whole_category():
    rules = ar.get_event_rules("cuoi_hoi")
    assert "kim_lau" not in rules  # kim_lau lives under lam_nha, not cuoi_hoi
    assert isinstance(rules, dict) and len(rules) > 0


def test_event_rules_month_filter_never_drops_a_block():
    unfiltered = ar.get_event_rules("lam_nha")
    filtered = ar.get_event_rules("lam_nha", lunar_month=3)
    assert set(filtered) == set(unfiltered)
    # A sample block's original fields all survive the annotation.
    block = filtered["nhung_ngay_tieu_hao"]
    assert block["note"] == unfiltered["nhung_ngay_tieu_hao"]["note"]
    assert block["theo_thang"] == unfiltered["nhung_ngay_tieu_hao"]["theo_thang"]
    assert block["source_pages"] == unfiltered["nhung_ngay_tieu_hao"]["source_pages"]


def test_event_rules_month_filter_picks_the_right_row():
    # database/events_rules.json lam_nha.nhung_ngay_tieu_hao: theo_thang list,
    # month 3 -> chi "Mùi".
    match = ar.get_event_rules("lam_nha", lunar_month=3)["nhung_ngay_tieu_hao"]["_match"]
    assert match == {"field": "theo_thang.thang", "rows": [{"thang": 3, "chi": "Mùi"}]}


def test_event_rules_month_filter_handles_grouped_month_keys():
    # entries as a dict keyed by grouped month-spec strings ("3+6+9", "1,5,9").
    ngu_mo = ar.get_event_rules("cuoi_hoi", lunar_month=9)["chiem_ngu_mo_bach_su_ky"]["_match"]
    assert ngu_mo["rows"] == [{"thang": "3+6+9", "gia_tri": ["Tý", "Tuất", "Thìn"]}]

    thien_hoa_v2 = ar.get_event_rules("lam_nha", lunar_month=5)["nhung_ngay_thien_hoa_ky_cat_lam_nha_v2"]["_match"]
    assert thien_hoa_v2["rows"] == [{"thang": "1,5,9", "gia_tri": "Tý (chuột già)"}]

    # entries as a list of dicts with a string quarter range ("4-5-6").
    tho_cam = ar.get_event_rules("an_tang", lunar_month=5)["nhung_ngay_tho_cam_ky_dao_gieng_chon_cat"]["_match"]
    assert tho_cam["rows"] == [{"thang": "4-5-6", "ngay": "Dần"}]

    # entries as a list of dicts with a literal int list ([1, 7]).
    thien_quan = ar.get_event_rules("xuat_hanh", lunar_month=7)["nhung_ngay_thien_quan_xuat_hanh_giao_dich_tot"]["_match"]
    assert thien_quan["rows"] == [{"thang": [1, 7], "ngay": "Tuất"}]


def test_event_rules_mua_exception_is_not_guessed():
    # lam_nha.gio_thien_la_dia_vong: Xuân's data sits under an unnamed
    # "cach_giai" key, not "mua_xuan" -- must not be guessed at.
    ha = ar.get_event_rules("lam_nha", lunar_month=5)["gio_thien_la_dia_vong"]
    assert ha["_match"]["rows"] == [{"khoa": "mua_ha", "gia_tri": ["Thìn", "Tuất"]}]

    xuan = ar.get_event_rules("lam_nha", lunar_month=2)["gio_thien_la_dia_vong"]
    assert xuan["_match"]["rows"] == []
    assert "cach_giai" not in xuan["_match"]["field"]
    assert xuan["cach_giai"] == ["Sửu", "Mùi"]  # still present verbatim


def test_event_rules_tuoi_and_prose_blocks_are_not_filtered():
    unfiltered = ar.get_event_rules("cuoi_hoi")
    filtered = ar.get_event_rules("cuoi_hoi", lunar_month=3)
    for key in ("gia_thu_bat_tuong", "nhung_ngay_bat_luong"):
        assert "_match" not in filtered[key]
        assert filtered[key] == unfiltered[key]

    unfiltered_lam_nha = ar.get_event_rules("lam_nha")
    filtered_lam_nha = ar.get_event_rules("lam_nha", lunar_month=3)
    for key in ("kim_lau", "bang_lap_thanh_tuoi_lam_nha", "cuc_thong_thien_khieu", "hoang_dao_hac_dao_theo_thang"):
        assert "_match" not in filtered_lam_nha[key]
        assert filtered_lam_nha[key] == unfiltered_lam_nha[key]


def test_event_rules_annotation_does_not_mutate_the_cache():
    ar.get_event_rules("lam_nha", lunar_month=3)
    assert "_match" not in ar.get_event_rules("lam_nha")["nhung_ngay_tieu_hao"]

    month_7 = ar.get_event_rules("lam_nha", lunar_month=7)["nhung_ngay_tieu_hao"]["_match"]
    assert month_7["rows"] == [{"thang": 7, "chi": "Hợi"}]


def test_event_rules_resolves_refs():
    lam_nha = ar.get_event_rules("lam_nha")
    two_path = lam_nha["ngu_hanh_tuong_sinh_khac"]["_ref"]
    assert set(two_path) == {"ngu_hanh_tuong_sinh", "ngu_hanh_tuong_khac"}

    an_tang = ar.get_event_rules("an_tang")
    assert an_tang["bai_tho_tho_tu_sat_chu"]["_ref"]  # trailing parenthetical still resolves
    bon_mua = an_tang["sat_chu_ve_bon_mua"]["_ref"]["sat_chu.he_theo_bon_mua"]
    assert bon_mua["xuan"] == "Thân"

    cuoi_hoi = ar.get_event_rules("cuoi_hoi")
    assert cuoi_hoi["huong_nha_nghinh_hon_theo_tuoi"]["_ref"]


def test_get_truc_resets_at_kien_and_steps_forward():
    # database/events_rules.json lam_nha.cach_tinh_ngay_truc: tiết-khí index 0
    # (Lập xuân) resets Trực Kiến at Chi Dần, then steps Trừ, Mãn, ... daily.
    kien = ar.get_truc(tiet_khi_index=0, day_chi="Dần")
    assert kien["truc"] == "Kiến"
    assert kien["tot_xau"] == "tot"

    tru = ar.get_truc(tiet_khi_index=0, day_chi="Mão")
    assert tru["truc"] == "Trừ"
    assert tru["tot_xau"] == "tot"

    # Phá is 6 steps after Kiến (Dần) -> Chi Thân; danh_gia_truc marks it xấu.
    pha = ar.get_truc(tiet_khi_index=0, day_chi="Thân")
    assert pha["truc"] == "Phá"
    assert pha["tot_xau"] == "xau"


def test_get_hoang_dao_hac_dao_ngay_wraps_by_month_pair():
    # database/events_rules.json lam_nha.hoang_dao_hac_dao_theo_thang: tháng
    # Giêng and tháng Bảy share the same row.
    thang_1 = ar.get_hoang_dao_hac_dao_ngay(1, "Tý")
    thang_7 = ar.get_hoang_dao_hac_dao_ngay(7, "Tý")
    assert thang_1["classification"] == thang_7["classification"] == "hoang_dao"

    assert ar.get_hoang_dao_hac_dao_ngay(1, "Ngọ")["classification"] == "hac_dao"


def test_get_xuat_hanh_dinh_cuc_looks_up_full_can_chi():
    entry = ar.get_xuat_hanh_dinh_cuc("Giáp Tý")
    assert entry["available"] is True
    assert entry["hy_than"] == "đông bắc"
    assert set(entry["gio_tot"]) == {"Sửu", "Dần", "Mão", "Tý"}

    assert ar.get_xuat_hanh_dinh_cuc("Không Tồn Tại")["available"] is False


if __name__ == "__main__":
    test_tam_nuong_day()
    test_non_bad_day_has_no_flags()
    test_duong_cong_ky_nhat_is_month_specific()
    test_kim_lau_matches_book_examples()
    test_kim_lau_unavailable_without_birth_year()
    test_cuc_thong_thien_khieu_birth_cuc_lookup()
    test_cuc_thong_thien_khieu_wraps_after_18()
    test_cuc_thong_thien_khieu_unavailable_without_age()
    test_trung_tang_gender_changes_direction()
    test_trung_tang_unavailable_without_birth_year()
    test_get_year_profile_returns_menh_and_direction()
    test_get_event_rules_returns_whole_category()
    test_event_rules_month_filter_never_drops_a_block()
    test_event_rules_month_filter_picks_the_right_row()
    test_event_rules_month_filter_handles_grouped_month_keys()
    test_event_rules_mua_exception_is_not_guessed()
    test_event_rules_tuoi_and_prose_blocks_are_not_filtered()
    test_event_rules_annotation_does_not_mutate_the_cache()
    test_event_rules_resolves_refs()
    test_get_truc_resets_at_kien_and_steps_forward()
    test_get_hoang_dao_hac_dao_ngay_wraps_by_month_pair()
    test_get_xuat_hanh_dinh_cuc_looks_up_full_can_chi()
    print("ok")
