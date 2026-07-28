import type { ChatHistory, ChatResponse } from "./types";

const BASE = "/api/v1";

async function json<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw new Error(detail.detail || `${res.status} ${res.statusText}`);
  }
  return res.json();
}

export function sendChatMessage(message: string, history: ChatHistory) {
  return fetch(`${BASE}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, history }),
  }).then(json<ChatResponse>);
}
