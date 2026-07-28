// Mirror of app/schemas.py.

export interface LunarDateInfo {
  day: number;
  month: number;
  year: number;
  is_leap_month: boolean;
  day_can_chi: string;
  month_can_chi: string;
  year_can_chi: string;
  year_menh: string;
  year_nap_am: string;
}

// The chat history blob is opaque -- round-tripped to the backend as-is,
// never inspected or constructed on the frontend.
export type ChatHistory = unknown[];

export interface ChatResponse {
  reply: string;
  lunar: LunarDateInfo | null;
  history: ChatHistory;
}

export interface ChatMessage {
  role: "user" | "assistant";
  text: string;
  lunar?: LunarDateInfo | null;
}
