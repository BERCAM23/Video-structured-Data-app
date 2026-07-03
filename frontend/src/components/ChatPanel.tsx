import { useEffect, useRef, useState } from "react";
import { chat, type ChatMessage } from "../lib/api";
import { splitCitations } from "../lib/time";

export default function ChatPanel({
  videoId, onSeek,
}: { videoId: string; onSeek: (s: number) => void }) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const send = async () => {
    const question = input.trim();
    if (!question || busy) return;
    setInput("");
    setBusy(true);
    const history: ChatMessage[] = [...messages, { role: "user", content: question }];
    setMessages([...history, { role: "assistant", content: "" }]);
    try {
      await chat(videoId, history, (chunk) => {
        setMessages((prev) => {
          const next = [...prev];
          const last = next[next.length - 1];
          next[next.length - 1] = { ...last, content: last.content + chunk };
          return next;
        });
      });
    } catch (e) {
      setMessages((prev) => {
        const next = [...prev];
        next[next.length - 1] = {
          role: "assistant",
          content: `Error: ${e instanceof Error ? e.message : "chat failed"}`,
        };
        return next;
      });
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="chatpanel">
      <div className="chatlog">
        {messages.length === 0 && (
          <p className="muted">
            Pregunta lo que quieras sobre esta transmision. Ejemplo: en que momento
            grito el narrador y que dijo exactamente?
          </p>
        )}
        {messages.map((m, i) => (
          <div key={i} className={`msg ${m.role}`}>
            {m.role === "assistant"
              ? splitCitations(m.content).map((p, j) =>
                  p.kind === "cite" ? (
                    <button key={j} className="cite" onClick={() => onSeek(p.seconds)}>
                      {p.value}
                    </button>
                  ) : (
                    <span key={j}>{p.value}</span>
                  ),
                )
              : m.content}
          </div>
        ))}
        <div ref={bottomRef} />
      </div>
      <form
        className="chatinput"
        onSubmit={(e) => { e.preventDefault(); send(); }}
      >
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Pregunta sobre el video..."
          disabled={busy}
        />
        <button type="submit" disabled={busy || !input.trim()}>
          {busy ? "..." : "Enviar"}
        </button>
      </form>
    </section>
  );
}
