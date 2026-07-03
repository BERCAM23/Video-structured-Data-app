export const API_BASE = "http://localhost:8000";

export type Status = {
  id: string;
  status: string;
  error: string | null;
  duration_s: number | null;
};

export type Records = {
  video: {
    id: string; title: string; duration_s: number; sport: string | null;
    teams: string | null; event_type: string | null; summary: string | null;
    status: string;
  };
  transcript_segments: { id: number; t_start: number; t_end: number; speaker: string; text: string }[];
  visual_events: { id: number; t_start: number; t_end: number; description: string; on_screen_text: string | null }[];
  minute_summaries: { id: number; minute_index: number; summary: string }[];
  key_moments: { id: number; t: number; title: string; description: string }[];
};

export type ChatMessage = { role: "user" | "assistant"; content: string };

async function ok(resp: Response): Promise<Response> {
  if (!resp.ok) throw new Error((await resp.text()) || `HTTP ${resp.status}`);
  return resp;
}

export async function uploadVideo(file: File): Promise<{ id: string }> {
  const form = new FormData();
  form.append("file", file);
  const resp = await ok(await fetch(`${API_BASE}/api/videos`, { method: "POST", body: form }));
  return resp.json();
}

export async function getStatus(id: string): Promise<Status> {
  return (await ok(await fetch(`${API_BASE}/api/videos/${id}/status`))).json();
}

export async function getRecords(id: string): Promise<Records> {
  return (await ok(await fetch(`${API_BASE}/api/videos/${id}`))).json();
}

export function streamUrl(id: string): string {
  return `${API_BASE}/api/videos/${id}/stream`;
}

export async function chat(
  id: string,
  messages: ChatMessage[],
  onChunk: (text: string) => void,
): Promise<void> {
  const resp = await ok(
    await fetch(`${API_BASE}/api/videos/${id}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ messages }),
    }),
  );
  const reader = resp.body!.getReader();
  const decoder = new TextDecoder();
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    onChunk(decoder.decode(value, { stream: true }));
  }
}
