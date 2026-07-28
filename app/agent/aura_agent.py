import os
from typing import Literal

from pydantic_ai import Agent

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
        "đến nó, hãy hỏi lại người dùng CHÍNH XÁC MỘT câu hỏi còn thiếu, đừng đoán hay bỏ qua.\n"
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
        "định được ngày nào (VD: bạn đang hỏi lại người dùng về ngày tháng)."
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
def get_kim_lau(birth_year: int, target_lunar_year: int) -> dict:
    """Check Kim Lâu (bad-luck age check for cưới hỏi/làm nhà) for a person given
    their birth year and the lunar year of the event."""
    return almanac_rules.get_kim_lau(birth_year, target_lunar_year)


@aura_agent.tool_plain
def get_cuc_thong_thien_khieu(birth_can_chi: str, age: int) -> dict:
    """Check the 18-cục cycle (used for làm nhà/cưới hỏi age suitability), given the
    person's birth-year Can-Chi and their current age."""
    return almanac_rules.get_cuc_thong_thien_khieu(birth_can_chi, age)


@aura_agent.tool_plain
def get_trung_tang(birth_year: int, death_lunar_year: int, gender: Literal["nam", "nu"]) -> dict:
    """Check Trùng Tang (used for an táng only) for the deceased, given their birth
    year, the lunar year of death, and their gender (direction of the count differs)."""
    return almanac_rules.get_trung_tang(birth_year, death_lunar_year, gender)
