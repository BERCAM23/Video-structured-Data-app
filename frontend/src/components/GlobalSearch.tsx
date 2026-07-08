import { useEffect, useRef, useState } from "react";
import { globalChat, type ChatMessage } from "../lib/api";
import { fmtTs, splitGlobalCitations } from "../lib/time";

export default function GlobalSearch({
  onOpenVideo,
}: { onOpenVideo: (title: string, seconds: number) => void }) {
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
      await globalChat(history, (chunk) => {
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
    <section className="globalsearch chatpanel">
      <div className="chatlog">
        {messages.length === 0 && (
          <p className="muted">
            Motor de busqueda sobre todo el archivo. Pregunta y te llevo al momento exacto.
          </p>
        )}
        {messages.map((m, i) => (
          <div key={i} className={`msg ${m.role}`}>
            {m.role === "assistant"
              ? splitGlobalCitations(m.content).map((p, j) =>
                  p.kind === "cite" ? (
                    <button
                      key={j}
                      className="cite"
                      onClick={() => onOpenVideo(p.title, p.seconds)}
                    >
                      {`▶ ${p.title} ${fmtTs(p.seconds)}`}
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
          placeholder="Busca en todas las transmisiones: quien dijo..., cuando paso..."
          disabled={busy}
        />
        <button type="submit" disabled={busy || !input.trim()}>
          {busy ? "..." : "Enviar"}
        </button>
      </form>
    </section>
  );
}
