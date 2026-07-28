from typing import Any

from pydantic import BaseModel


class LunarDateInfo(BaseModel):
    day: int
    month: int
    year: int
    is_leap_month: bool
    day_can_chi: str
    month_can_chi: str
    year_can_chi: str
    year_menh: str
    year_nap_am: str


class ChatReply(BaseModel):
    message: str
    lunar: LunarDateInfo | None = None


class ChatRequest(BaseModel):
    message: str
    history: list[dict[str, Any]] = []


class ChatResponse(BaseModel):
    reply: str
    lunar: LunarDateInfo | None = None
    history: list[dict[str, Any]]
