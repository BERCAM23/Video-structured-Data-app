import { useEffect, useMemo, useRef, useState } from "react";
import type { Records } from "../lib/api";
import { fmtTs } from "../lib/time";

type Tab = "transcript" | "visual" | "moments";

type Item = { key: string; t: number; end: number; head: string; body: string };

export default function DataScroller({
  records, currentTime, onSeek,
}: { records: Records; currentTime: number; onSeek: (s: number) => void }) {
  const [tab, setTab] = useState<Tab>("transcript");
  const [follow, setFollow] = useState(true);
  const listRef = useRef<HTMLDivElement>(null);

  const items: Item[] = useMemo(() => {
    if (tab === "transcript") {
      return records.transcript_segments.map((s) => ({
        key: `t${s.id}`, t: s.t_start, end: s.t_end, head: s.speaker, body: s.text,
      }));
    }
    if (tab === "visual") {
      return records.visual_events.map((e) => ({
        key: `v${e.id}`, t: e.t_start, end: e.t_end,
        head: e.on_screen_text ?? "", body: e.description,
      }));
    }
    return records.key_moments.map((k) => ({
      key: `m${k.id}`, t: k.t, end: k.t + 1, head: k.title, body: k.description,
    }));
  }, [tab, records]);

  const activeIdx = useMemo(() => {
    let idx = -1;
    for (let i = 0; i < items.length; i++) {
      if (items[i].t <= currentTime) idx = i;
      else break;
    }
    return idx;
  }, [items, currentTime]);

  useEffect(() => {
    if (!follow) return;
    const list = listRef.current;
    const el = list?.querySelector<HTMLElement>(`[data-idx="${activeIdx}"]`);
    if (!list || !el) return;
    const target = el.offsetTop - list.clientHeight / 2 + el.clientHeight / 2;
    list.scrollTo({ top: Math.max(0, target), behavior: "smooth" });
  }, [activeIdx, follow]);

  return (
    <aside className="scroller">
      <nav className="tabs">
        {(["transcript", "visual", "moments"] as Tab[]).map((t) => (
          <button key={t} className={tab === t ? "on" : ""} onClick={() => setTab(t)}>
            {t === "transcript" ? "Transcripcion" : t === "visual" ? "Visual" : "Momentos"}
          </button>
        ))}
        <button className={follow ? "on" : ""} onClick={() => setFollow((f) => !f)}>
          Seguir
        </button>
      </nav>
      <div className="list" ref={listRef}>
        {items.map((it, i) => (
          <button
            key={it.key}
            data-idx={i}
            className={`item ${i === activeIdx ? "active" : ""}`}
            onClick={() => onSeek(it.t)}
          >
            <span className="ts">{fmtTs(it.t)}</span>
            <span className="content">
              {it.head && <b>{it.head} </b>}
              {it.body}
            </span>
          </button>
        ))}
      </div>
    </aside>
  );
}
