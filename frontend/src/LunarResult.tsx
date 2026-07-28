import type { LunarDateInfo } from "./types";

export default function LunarResult({ lunar }: { lunar: LunarDateInfo }) {
  return (
    <div className="lunar-card">
      <div className="lunar-headline">
        {lunar.day}/{lunar.month}
        {lunar.is_leap_month ? " (nhuận)" : ""}/{lunar.year} âm lịch
      </div>
      <dl className="lunar-grid">
        <dt>Ngày</dt>
        <dd>{lunar.day_can_chi}</dd>
        <dt>Tháng</dt>
        <dd>{lunar.month_can_chi}</dd>
        <dt>Năm</dt>
        <dd>{lunar.year_can_chi}</dd>
        <dt>Mệnh</dt>
        <dd>{lunar.year_menh}</dd>
        <dt>Nạp âm</dt>
        <dd>{lunar.year_nap_am}</dd>
      </dl>
    </div>
  );
}
