import { useEffect, useRef, useState } from "react";
import { sendChatMessage } from "./api";
import LunarResult from "./LunarResult";
import type { ChatHistory, ChatMessage } from "./types";

export default function ChatWindow() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [history, setHistory] = useState<ChatHistory>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, sending]);

  async function handleSend() {
    const text = input.trim();
    if (!text || sending) return;

    setInput("");
    setError(null);
    setMessages((prev) => [...prev, { role: "user", text }]);
    setSending(true);

    try {
      const res = await sendChatMessage(text, history);
      setMessages((prev) => [...prev, { role: "assistant", text: res.reply, lunar: res.lunar }]);
      setHistory(res.history);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Đã có lỗi xảy ra, vui lòng thử lại.");
    } finally {
      setSending(false);
    }
  }

  return (
    <>
      <div className="chat" ref={scrollRef}>
        {messages.length === 0 && (
          <div className="empty-state">
            <span className="wordmark">
              A<b>u</b>ra
            </span>
            Hỏi mình về một ngày âm lịch, xem tuổi làm nhà, cưới hỏi, an táng hay xuất hành —
            dựa theo Ngọc Hạp Thông Thư. Ví dụ: "Ngày 15/8/2026 cưới có tốt không, tôi sinh
            năm 1995?"
          </div>
        )}
        {messages.map((m, i) => (
          <div key={i} className={`msg-row ${m.role}`}>
            <div className="bubble">{m.text}</div>
            {m.lunar && <LunarResult lunar={m.lunar} />}
          </div>
        ))}
        {sending && (
          <div className="msg-row assistant">
            <div className="bubble pending">Đang tra cứu…</div>
          </div>
        )}
      </div>

      {error && <div className="error-banner">{error}</div>}

      <div className="composer">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              handleSend();
            }
          }}
          placeholder="Nhập câu hỏi của bạn…"
          disabled={sending}
        />
        <button onClick={handleSend} disabled={sending || !input.trim()}>
          Gửi
        </button>
      </div>
    </>
  );
}
