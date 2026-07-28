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


def test_trung_tang_gender_changes_direction():
    nam = ar.get_trung_tang(birth_year=2000, death_lunar_year=2026, gender="nam")
    nu = ar.get_trung_tang(birth_year=2000, death_lunar_year=2026, gender="nu")
    assert nam["landing_chi"] != nu["landing_chi"]
    assert nam["zone"] in ("thien_di", "nhap_mo", "trung_tang")
    assert nu["zone"] in ("thien_di", "nhap_mo", "trung_tang")
    assert isinstance(nam["source_pages"], list) and all(isinstance(p, int) for p in nam["source_pages"])


def test_get_year_profile_returns_menh_and_direction():
    profile = ar.get_year_profile("Giáp Tý")
    assert profile["menh"] == "Kim"
    assert profile["nap_am"] == "Vàng dưới biển"


def test_get_event_rules_returns_whole_category():
    rules = ar.get_event_rules("cuoi_hoi")
    assert "kim_lau" not in rules  # kim_lau lives under lam_nha, not cuoi_hoi
    assert isinstance(rules, dict) and len(rules) > 0


if __name__ == "__main__":
    test_tam_nuong_day()
    test_non_bad_day_has_no_flags()
    test_duong_cong_ky_nhat_is_month_specific()
    test_kim_lau_matches_book_examples()
    test_cuc_thong_thien_khieu_birth_cuc_lookup()
    test_cuc_thong_thien_khieu_wraps_after_18()
    test_trung_tang_gender_changes_direction()
    test_get_year_profile_returns_menh_and_direction()
    test_get_event_rules_returns_whole_category()
    print("ok")
