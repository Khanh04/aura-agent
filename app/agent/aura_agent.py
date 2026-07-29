import os
from datetime import date, timedelta
from typing import Literal

from pydantic_ai import Agent, ModelRetry

from app.config import settings
from app.schemas import ChatReply, LunarDateInfo
from app.services import almanac_rules, lunar_calendar

# pydantic-ai's google-gla provider reads this env var directly.
os.environ.setdefault("GEMINI_API_KEY", settings.GEMINI_API_KEY)


aura_agent = Agent(
    "google:gemini-flash-lite-latest",
    output_type=ChatReply,
    instructions=(
        "Bạn là Aura, một trợ lý tra cứu Ngọc Hạp Thông Thư (lịch âm và phong tục Việt Nam). "
        "Bạn chỉ trả lời dựa trên dữ liệu lấy được từ các công cụ (tools) -- không dùng kiến thức "
        "chung chung đã học được, vì mục đích của bạn là bám sát đúng nội dung cuốn sách này.\n\n"
        "QUY TẮC:\n"
        "1. Luôn gọi 'convert_date' để đổi ngày dương lịch sang âm lịch trước khi tra cứu bất kỳ "
        "quy tắc nào -- không tự tính toán ngày âm lịch. Chỉ gọi 'convert_date' với một ngày ISO "
        "(YYYY-MM-DD) rõ ràng, không mơ hồ; nếu người dùng nói ngày tương đối ('hôm nay', 'tuần sau'), "
        "hãy tự quy đổi sang ngày ISO cụ thể dựa vào ngày hiện tại được cung cấp trong tin nhắn trước "
        "khi gọi tool.\n"
        "2. Sách chỉ có dữ liệu chi tiết cho 4 loại sự kiện: cuoi_hoi (cưới hỏi), lam_nha (làm nhà/xây "
        "dựng), an_tang (an táng/tang lễ), xuat_hanh (xuất hành/đi xa). Khi người dùng hỏi về một việc "
        "khác (VD: khai trương, ký hợp đồng), hãy tự suy luận xem việc đó gần với loại nào nhất trong 4 "
        "loại trên, dùng loại đó để tra cứu, và LUÔN nói rõ với người dùng rằng đây là một sự suy luận "
        "gần đúng (ví dụ: 'Sách không có mục riêng cho khai trương, mình tạm dùng quy tắc xuất hành vì "
        "gần nghĩa nhất') -- không được ngầm coi một việc không được ghi trong sách là được ghi.\n"
        "3. Một số quy tắc phụ thuộc vào tuổi (và với an táng, cả giới tính) của người liên quan: Kim "
        "Lâu và Cục Thông Thiên Khiếu (dùng cho cưới hỏi/làm nhà) cần năm sinh; Trùng Tang (dùng cho an "
        "táng) cần năm sinh VÀ giới tính (nam/nữ) của người mất. Nếu thiếu thông tin này và câu hỏi cần "
        "đến nó, hãy hỏi lại người dùng CHÍNH XÁC MỘT câu hỏi còn thiếu, đừng đoán hay bỏ qua. TUYỆT ĐỐI "
        "KHÔNG được tự bịa, ước lượng, hay suy đoán năm sinh/tuổi từ ngữ cảnh (VD: đoán 'bố' nghĩa là "
        "sinh khoảng năm nào đó) rồi gọi 'get_kim_lau'/'get_cuc_thong_thien_khieu'/'get_trung_tang' với "
        "con số bịa ra đó -- nếu người dùng chưa nói rõ năm sinh bằng một con số cụ thể, PHẢI dừng lại "
        "và hỏi trước khi gọi 3 tool này. Ngược lại, suy luận giới tính từ từ xưng hô người dùng đã dùng "
        "(bố/ông/anh -> nam; mẹ/bà/chị -> nữ) là hợp lệ, không cần hỏi lại riêng về giới tính trong "
        "trường hợp đó.\n"
        "4. Một số quy tắc trong sách tự mâu thuẫn với nhau (sách ghi nhiều dị bản, có 'luu_y'/"
        "'variant_of' về sự mâu thuẫn hoặc dị bản). Khi gặp trường hợp này, hãy nói rõ sự mâu thuẫn "
        "thay vì chọn đại một bên.\n"
        "5. Luôn trích dẫn quy tắc/số trang nguồn (source_pages) mà bạn dùng để trả lời, để người dùng "
        "có thể tra lại. Mỗi quy tắc con trong kết quả 'get_event_rules' có trường 'applies_by' cho biết "
        "nó được phân theo tháng/mùa/tuổi/nhóm tuổi/cục (thang/mua/tuoi/nhom_tuoi/cuc) hay không có cách "
        "phân loại cụ thể (ref/status/prose/none) -- dùng trường này để biết cách đối chiếu quy tắc với "
        "ngày âm lịch đã xác định.\n"
        "6. Nếu không đủ dữ liệu để trả lời chắc chắn, hãy nói thẳng là không đủ dữ liệu, đừng bịa.\n"
        "7. Trả lời bằng văn bản thuần (plain text) -- KHÔNG dùng cú pháp Markdown (không **in đậm**, "
        "không dùng dấu * hay - để gạch đầu dòng); giao diện hiển thị nguyên văn, không render Markdown.\n"
        "8. Trường 'lunar' trong kết quả trả về: LUÔN điền đầy đủ trường này bằng kết quả gọi "
        "'convert_date' bất kỳ khi nào bạn đã xác định được một ngày dương lịch cụ thể trong lượt trả "
        "lời này (kể cả khi câu trả lời còn thiếu thông tin khác). Chỉ để trống khi lượt này chưa xác "
        "định được ngày nào (VD: bạn đang hỏi lại người dùng về ngày tháng).\n"
        "9. Khi người dùng nhờ chọn/tìm ngày tốt trong một khoảng thời gian (không phải một "
        "ngày cụ thể), hãy tự quy đổi khoảng đó sang một khoảng ngày dương lịch ISO cụ thể "
        "(như cách quy tắc 1 xử lý ngày tương đối). Nếu khoảng quá rộng (quá 60 ngày), không "
        "rõ ràng ('năm sau', 'quý 3'), HOẶC người dùng không nói khoảng thời gian nào cả (VD: "
        "'chọn giúp tôi ngày đẹp'), hãy hỏi lại người dùng để xác định/thu hẹp khoảng trước khi "
        "gọi tool -- TUYỆT ĐỐI KHÔNG tự chọn một khoảng mặc định (VD: hôm nay + 60 ngày) rồi trả "
        "lời luôn. Gọi 'get_candidate_days' một lần cho khoảng đã thu hẹp; nếu cần đối chiếu sao "
        "tốt/xấu cho (các) ngày có khả năng cao, gọi thêm 'get_star_info' riêng cho từng ngày "
        "đó. Luôn gọi 'get_event_rules' cho loại sự kiện liên quan để đối chiếu, và áp dụng "
        "quy tắc 3 nếu cần thông tin riêng của người liên quan. Chọn ra 1-3 ngày tốt nhất kèm "
        "lý do và trích dẫn nguồn; cuối cùng gọi 'convert_date' cho ngày được đề xuất tốt "
        "nhất để điền trường 'lunar' theo quy tắc 8 (trường 'lunar' chỉ chứa một ngày).\n"
        "10. Khi người dùng hỏi chung chung về một ngày tốt/xấu ra sao (VD: 'hôm nay ngày "
        "tốt hay xấu?', hỏi về Trực, hỏi về Hoàng Đạo/Hắc Đạo) mà KHÔNG gắn với một trong 4 "
        "loại sự kiện ở quy tắc 2, đừng ép về một trong 4 loại đó -- hãy tra cứu trực tiếp "
        "bằng CẢ 4 tool sau, mỗi tool trả lời một khái niệm KHÁC NHAU, không thể suy ra cái "
        "này từ cái kia: 'get_truc' (Trực -- BẮT BUỘC gọi tool này nếu câu hỏi có nhắc đến "
        "Trực; tên sao trong 'get_star_info' dù có chữ 'hoàng đạo' KHÔNG phải là Trực, không "
        "được dùng để suy đoán Trực), 'get_hoang_dao_hac_dao_ngay' (Hoàng Đạo/Hắc Đạo -- BẮT "
        "BUỘC gọi tool này nếu câu hỏi có nhắc đến Hoàng Đạo/Hắc Đạo, không được suy đoán từ "
        "tên sao), 'get_star_info' (sao tốt/xấu), và 'get_global_bad_days' (Tam Nương/Nguyệt "
        "Kỵ/Dương Công). Nếu người dùng hỏi thêm về hướng/giờ xuất hành, gọi thêm "
        "'get_xuat_hanh_dinh_cuc'. Chỉ suy luận sang một trong 4 loại sự kiện khi người dùng "
        "nêu rõ một việc cụ thể cần làm."
    ),
)


@aura_agent.tool_plain
def convert_date(gregorian_date: str) -> LunarDateInfo:
    """Convert an unambiguous ISO Gregorian date (YYYY-MM-DD) to its Vietnamese lunar
    equivalent, including day/month/year Can-Chi and the year's menh/nap_am."""
    year, month, day = (int(p) for p in gregorian_date.split("-"))
    lunar = lunar_calendar.solar_to_lunar(day, month, year)
    year_profile = lunar_calendar.get_can_chi_for_year(lunar["year"])
    return LunarDateInfo(
        day=lunar["day"],
        month=lunar["month"],
        year=lunar["year"],
        is_leap_month=lunar["is_leap_month"],
        day_can_chi=lunar_calendar.get_can_chi_for_day(lunar["jd"]),
        month_can_chi=lunar_calendar.get_can_chi_for_month(lunar["month"], lunar["year"]),
        year_can_chi=year_profile["can_chi"],
        year_menh=year_profile["menh"],
        year_nap_am=year_profile["nap_am"],
    )


@aura_agent.tool_plain
def get_global_bad_days(lunar_day: int, lunar_month: int | None = None) -> list[dict]:
    """Look up universal bad-day rules (Tam Nương, Nguyệt Kỵ, Dương Công) that apply
    to a given lunar day-of-month, independent of the event type."""
    return almanac_rules.get_global_bad_day_flags(lunar_day, lunar_month)


@aura_agent.tool_plain
def get_event_rules(event_type: Literal["cuoi_hoi", "lam_nha", "an_tang", "xuat_hanh"]) -> dict:
    """Fetch all curated almanac rules for one of the 4 known event categories
    (cuoi_hoi=wedding, lam_nha=house-building, an_tang=burial, xuat_hanh=travel)."""
    return almanac_rules.get_event_rules(event_type)


@aura_agent.tool_plain
def get_star_info(day_chi: str, lunar_month: int) -> dict:
    """Look up auspicious/inauspicious stars active on a day, given the day's Chi
    (branch, e.g. 'Tý') and the lunar month."""
    return almanac_rules.get_star_info(day_chi, lunar_month)


@aura_agent.tool_plain
def get_year_profile(can_chi_year: str) -> dict:
    """Look up a year's menh/nap_am, directional luck, and Tam Tai Han exposure,
    given the year's Can-Chi string (e.g. 'Giáp Tý')."""
    return almanac_rules.get_year_profile(can_chi_year)


@aura_agent.tool_plain
def get_kim_lau(birth_year: int | None, target_lunar_year: int) -> dict:
    """Check Kim Lâu (bad-luck age check for cưới hỏi/làm nhà) for a person given
    their birth year and the lunar year of the event. birth_year is the user's
    ACTUAL stated birth year as a number -- if they haven't given one in this
    conversation, pass birth_year=None (do NOT guess/estimate/invent a number)
    and then ask them for it in your text reply; the tool will return
    'available': False for None, which is the correct, honest result when the
    real value isn't known. When explaining an 'available': True result,
    describe it using this tool's own 'remainder_mod_10' field (tuổi mụ chia
    dư cho 10) -- do NOT say "chia 9"/mod 9 even though the book's prose
    claims that; that prose is a known mistranscription (see
    almanac_rules.get_kim_lau's docstring)."""
    return almanac_rules.get_kim_lau(birth_year, target_lunar_year)


@aura_agent.tool_plain
def get_cuc_thong_thien_khieu(birth_can_chi: str, age: int | None) -> dict:
    """Check the 18-cục cycle (used for làm nhà/cưới hỏi age suitability), given the
    person's birth-year Can-Chi and their current age. age is the user's
    ACTUAL stated age/birth year as a number -- if they haven't given one in
    this conversation, pass age=None (do NOT guess/estimate/invent a number)
    and then ask them for it in your text reply; the tool will return
    'available': False for None, which is the correct, honest result when the
    real value isn't known."""
    return almanac_rules.get_cuc_thong_thien_khieu(birth_can_chi, age)


@aura_agent.tool_plain
def get_trung_tang(birth_year: int | None, death_lunar_year: int, gender: Literal["nam", "nu"]) -> dict:
    """Check Trùng Tang (used for an táng only) for the deceased, given their birth
    year, the lunar year of death, and their gender (direction of the count differs).
    birth_year is the user's ACTUAL stated birth year as a number -- if they
    haven't given one in this conversation, pass birth_year=None (do NOT
    guess/estimate/invent a number) and then ask them for it in your text
    reply; the tool will return 'available': False for None, which is the
    correct, honest result when the real value isn't known. Gender inferred
    from a kinship term the user already used (bố/ông/anh -> nam; mẹ/bà/chị
    -> nữ) is fine to use without asking."""
    return almanac_rules.get_trung_tang(birth_year, death_lunar_year, gender)


@aura_agent.tool_plain
def get_truc(gregorian_date: str, day_chi: str) -> dict:
    """The ONLY source of truth for Trực (the 12-day Kiến-Trừ-Mãn-Bình...
    cycle). Whenever the user asks about Trực for a day, call this tool --
    star names from get_star_info (even ones containing "hoàng đạo") are a
    different concept and must never be used to guess Trực."""
    year, month, day = (int(p) for p in gregorian_date.split("-"))
    jd = lunar_calendar.solar_to_lunar(day, month, year)["jd"]
    tiet_khi_index = lunar_calendar.get_tiet_khi_index(jd)
    return almanac_rules.get_truc(tiet_khi_index, day_chi)


@aura_agent.tool_plain
def get_hoang_dao_hac_dao_ngay(lunar_month: int, day_chi: str) -> dict:
    """The ONLY source of truth for whether a day is Hoàng Đạo (auspicious)
    or Hắc Đạo (inauspicious). Whenever the user asks about Hoàng Đạo/Hắc
    Đạo for a day, call this tool -- do not infer the answer from star names
    returned by get_star_info, which is a separate, less reliable table.
    IMPORTANT: the book's table only classifies 8 of the 12 Chi per month --
    when 'classification' comes back null/None, that means the book does NOT
    classify this day either way. You MUST say the book has no Hoàng
    Đạo/Hắc Đạo data for this day -- do NOT default to calling it Hoàng Đạo
    or Hắc Đạo, and do NOT guess based on other tools' data."""
    return almanac_rules.get_hoang_dao_hac_dao_ngay(lunar_month, day_chi)


@aura_agent.tool_plain
def get_xuat_hanh_dinh_cuc(day_can_chi: str) -> dict:
    """Look up Hỷ thần/Kế thần/Tài thần directions, Không Vong days, and giờ
    tốt for xuất hành, given the day's full Can-Chi (e.g. 'Giáp Tý')."""
    return almanac_rules.get_xuat_hanh_dinh_cuc(day_can_chi)


@aura_agent.tool_plain
def get_candidate_days(start_date: str, end_date: str) -> list[dict]:
    """Scan every day in an inclusive ISO date range (max 60 days) and return each
    day's lunar date, Can-Chi, and universal bad-day flags (Tam Nương/Nguyệt Kỵ/Dương
    Công) -- for picking a good day within a period. Does NOT include star_info
    (call 'get_star_info' per shortlisted candidate) or event-specific rules (call
    'get_event_rules' separately) -- combine all three to recommend specific days.
    Do NOT call this with a range you picked yourself (a default window, or a
    narrower guess after a too-wide range was rejected) when the user hasn't
    confirmed a specific range -- ask them in your text reply instead."""
    start = date.fromisoformat(start_date)
    end = date.fromisoformat(end_date)
    try:
        lunar_days = lunar_calendar.solar_range_to_lunar(start, end)
    except ValueError as e:
        raise ModelRetry(str(e)) from e

    return [
        {
            "gregorian_date": (start + timedelta(days=i)).isoformat(),
            "lunar_day": lunar["day"],
            "lunar_month": lunar["month"],
            "lunar_year": lunar["year"],
            "is_leap_month": lunar["is_leap_month"],
            "day_can_chi": lunar_calendar.get_can_chi_for_day(lunar["jd"]),
            "bad_day_flags": almanac_rules.get_global_bad_day_flags(lunar["day"], lunar["month"]),
        }
        for i, lunar in enumerate(lunar_days)
    ]
