import { useState, type FormEvent } from "react";
import { PaperPlaneTilt, Robot } from "@phosphor-icons/react";
import { PageHeader, Panel } from "../components/ui";
import { request } from "../lib/api";
import type { AIChatResponse } from "../types";

type Message = { role: "user" | "assistant"; text: string; details?: AIChatResponse };

const suggestions = [
  "Tóm tắt doanh thu 30 ngày gần nhất",
  "Sản phẩm nào bán chạy nhất tháng này?",
  "Nguyên liệu nào đang tồn thấp và nên ưu tiên nhập?",
];

export function AssistantPage() {
  const [message, setMessage] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function send(event?: FormEvent, suggested?: string) {
    event?.preventDefault();
    const text = (suggested ?? message).trim();
    if (!text || loading) return;
    setMessages((current) => [...current, { role: "user", text }]);
    setMessage("");
    setError("");
    setLoading(true);
    try {
      const response = await request<AIChatResponse>("/ai/chat", {
        method: "POST",
        body: JSON.stringify({ message: text }),
      });
      setMessages((current) => [
        ...current,
        { role: "assistant", text: response.answer, details: response },
      ]);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Không thể nhận phản hồi AI");
    } finally {
      setLoading(false);
    }
  }

  return <>
    <PageHeader title="Trợ lý quản lý" description="Phân tích báo cáo chỉ đọc. Mọi số liệu chính xác được tính bởi backend." />
    <div className="grid gap-5 xl:grid-cols-[1fr_18rem]">
      <Panel className="flex min-h-[34rem] flex-col overflow-hidden">
        <div className="flex-1 space-y-4 overflow-y-auto p-5" aria-live="polite">
          {messages.length === 0 && <div className="state flex-col text-stone-500"><Robot size={38} /><span>Hỏi về doanh thu, sản phẩm bán chạy hoặc tồn kho thấp.</span></div>}
          {messages.map((item, index) => <div key={index} className={`max-w-3xl rounded-xl p-4 ${item.role === "user" ? "ml-auto bg-coffee text-white" : "bg-stone-100"}`}><p className="m-0 whitespace-pre-wrap">{item.text}</p>{item.details && <><ul className="mt-3 space-y-1 text-sm">{item.details.highlights.map((line) => <li key={line}>• {line}</li>)}</ul>{item.details.recommendations.length > 0 && <div className="mt-4 border-t border-stone-200 pt-3"><strong className="text-sm">Gợi ý cần xác nhận</strong><ul className="mt-2 space-y-1 text-sm">{item.details.recommendations.map((line) => <li key={line}>• {line}</li>)}</ul></div>}<p className="mt-3 text-xs text-stone-500">Nguồn: {item.details.tools_used.join(", ") || "không dùng công cụ"}</p></>}</div>)}
          {loading && <div className="flex items-center gap-2 text-sm text-stone-500"><Robot className="animate-pulse" />Đang phân tích dữ liệu…</div>}
        </div>
        <form className="border-t border-stone-200 p-4" onSubmit={(event) => void send(event)}>
          <label className="label" htmlFor="assistant-message">Câu hỏi</label>
          <div className="flex gap-2"><textarea id="assistant-message" className="field min-h-20 resize-y" maxLength={2000} value={message} onChange={(event) => setMessage(event.target.value)} placeholder="Ví dụ: Doanh thu tháng này thế nào?" /><button className="btn btn-primary self-end" disabled={loading || !message.trim()}><PaperPlaneTilt size={20} />Gửi</button></div>
          {error && <p role="alert" className="mt-2 text-sm text-red-700">{error}</p>}
        </form>
      </Panel>
      <Panel className="h-fit p-4"><h2 className="font-serif text-lg font-bold">Câu hỏi gợi ý</h2><div className="mt-3 space-y-2">{suggestions.map((suggestion) => <button key={suggestion} className="btn w-full justify-start text-left text-sm" type="button" disabled={loading} onClick={() => void send(undefined, suggestion)}>{suggestion}</button>)}</div><p className="mt-4 text-xs leading-5 text-stone-500">Trợ lý không thể sửa dữ liệu, chạy SQL, đặt hàng hoặc thực hiện thanh toán.</p></Panel>
    </div>
  </>;
}
