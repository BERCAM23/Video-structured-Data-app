export function fmtTs(seconds: number): string {
  const total = Math.floor(seconds);
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = total % 60;
  const mm = String(m).padStart(2, "0");
  const ss = String(s).padStart(2, "0");
  return h ? `${h}:${mm}:${ss}` : `${mm}:${ss}`;
}

const CITE_RE = /\[(?:(\d{1,2}):)?(\d{1,2}):(\d{2})\]/g;

export type Part =
  | { kind: "text"; value: string }
  | { kind: "cite"; value: string; seconds: number };

export function splitCitations(text: string): Part[] {
  const parts: Part[] = [];
  let last = 0;
  for (const m of text.matchAll(CITE_RE)) {
    const idx = m.index ?? 0;
    if (idx > last) parts.push({ kind: "text", value: text.slice(last, idx) });
    const h = m[1] ? parseInt(m[1], 10) : 0;
    const seconds = h * 3600 + parseInt(m[2], 10) * 60 + parseInt(m[3], 10);
    parts.push({ kind: "cite", value: m[0], seconds });
    last = idx + m[0].length;
  }
  if (last < text.length) parts.push({ kind: "text", value: text.slice(last) });
  return parts;
}

const GLOBAL_CITE_RE = /\[([^\[\]@]+?) @ (?:(\d{1,2}):)?(\d{1,2}):(\d{2})\]/g;

export type GlobalPart =
  | { kind: "text"; value: string }
  | { kind: "cite"; value: string; title: string; seconds: number };

export function splitGlobalCitations(text: string): GlobalPart[] {
  const parts: GlobalPart[] = [];
  let last = 0;
  for (const m of text.matchAll(GLOBAL_CITE_RE)) {
    const idx = m.index ?? 0;
    if (idx > last) parts.push({ kind: "text", value: text.slice(last, idx) });
    const title = m[1].trim();
    const h = m[2] ? parseInt(m[2], 10) : 0;
    const seconds = h * 3600 + parseInt(m[3], 10) * 60 + parseInt(m[4], 10);
    parts.push({ kind: "cite", value: m[0], title, seconds });
    last = idx + m[0].length;
  }
  if (last < text.length) parts.push({ kind: "text", value: text.slice(last) });
  return parts;
}
