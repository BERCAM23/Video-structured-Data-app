# Video Intelligence MVP - Design Spec

Date: 2026-07-02
Status: Approved by Bernardo
Deadline: demo ready to work by 2026-07-05 (3 days)

## Goal

Process one real Fox Sports LatAm video (Spanish) into structured data and let an AI answer questions about it, grounded in that data, with clickable timestamp citations. This demo sells the production service to the cousin's boss.

## Architecture Decision

Hybrid, best tool per job. Chosen over all-Gemini (weak diarization kills the "who said it" query) and all-Anthropic (3-5x visual cost plus frame-extraction code we don't have time for).

| Job | Tool | Model / API | Cost per hour of video |
|---|---|---|---|
| Diarized Spanish transcript | ElevenLabs Scribe v2 | batch STT API, webhook or poll | $0.22 |
| Visual analysis | Google Gemini | `gemini-3.5-flash`, native video input via File API | ~$1.00 |
| Summaries + classification | Google Gemini | `gemini-3.5-flash` (text only) | ~$0.15 |
| Q&A chat | Anthropic Claude | `claude-opus-4-8`, prompt caching | $0.01-0.10 per question |

Total processing: ~$1.40/hr on demand. ~$0.90/hr with Gemini batch mode (50% off) at production scale.

Fallback for transcription: AssemblyAI Universal-3.5 Pro at $0.23/hr (explicitly documents Spanish diarization; has an experimental high-accuracy diarization mode at +$0.065/hr if Scribe struggles with overlapping commentators).

## Pipeline (per video)

Stages run in this order. Each stage writes its output to disk before the next starts. Re-running skips completed stages. Every external call retries 3x with exponential backoff.

1. **Ingest.** Accept MP4 upload. Store under `data/videos/{video_id}/source.mp4`. Probe duration and validate with ffmpeg.
2. **Audio extraction.** ffmpeg extracts mono 16kHz audio track to `audio.mp3`.
3. **Transcription.** Send audio to ElevenLabs Scribe v2 batch endpoint. Output: utterances with speaker labels, word-level timestamps, audio events. Save raw response, then normalize into `transcript_segments`.
4. **Visual analysis.** Upload video to Gemini File API (2 GB limit, 48h retention, fine for MVP). Split analysis into 15-minute windows processed in parallel (Gemini's 64K output cap makes whole-video single calls unreliable). Prompt per window: describe what is happening on screen every ~4 seconds, read on-screen graphics (score, clock, player names), flag notable moments. Structured JSON output with absolute timestamps (window offset added).
5. **Merge + summarize.** Merge transcript and visual events on the timeline. One `gemini-3.5-flash` text call per 10 minutes of merged data produces `minute_summaries` and candidate `key_moments`. One final call produces the whole-video summary and classification.
6. **Persist.** All records land in SQLite (`data/vault.db`) plus a per-video JSON export (`data/videos/{video_id}/records.json`).

Speaker naming: Scribe returns anonymous labels (speaker_1, speaker_2). The summarize stage maps labels to real names when the transcript itself reveals them (commentators address each other by name). Unmapped speakers stay as labels. The UI allows manual rename; renames propagate to the records.

## Data Model (SQLite)

All timestamps are float seconds from video start. All tables carry `video_id`.

- `videos`: id, title, filename, duration_s, sport, teams, event_type, summary, status (stage progress), created_at
- `transcript_segments`: id, video_id, t_start, t_end, speaker, text
- `words` (optional detail table): segment_id, t_start, t_end, word
- `visual_events`: id, video_id, t_start, t_end, description, on_screen_text
- `minute_summaries`: id, video_id, minute_index, summary
- `key_moments`: id, video_id, t, title, description

This schema is the context vault format. Production adds Postgres + pgvector and embeddings columns; the record shapes do not change.

## Grounded Chat

- Model: `claude-opus-4-8`, streaming, `thinking: {type: "adaptive"}` set explicitly.
- Context: the video's full records serialized compactly (transcript + visual events + summaries + moments), placed in the system prompt with `cache_control` so repeat questions hit the prompt cache. A 2-hour broadcast is roughly 100-150K tokens; fits in the 1M window.
- Rules enforced by system prompt: answer only from the records; every factual claim cites `[MM:SS]` or `[HH:MM:SS]`; say "not in the data" instead of guessing; answer in the user's language (Spanish or English).
- The frontend parses `[MM:SS]` citations into buttons that seek the player.
- No vector DB in MVP. Single video, full context beats retrieval on accuracy. Production: pgvector hybrid search across the whole vault.

## Web App

Backend: Python 3.11+, FastAPI, uvicorn. SQLite via sqlite3 or SQLModel. Endpoints:

- `POST /api/videos` - multipart upload, creates video record, starts pipeline as background task
- `GET /api/videos/{id}/status` - stage-by-stage progress for the processing screen
- `GET /api/videos/{id}` - all structured records
- `POST /api/videos/{id}/chat` - SSE streaming chat; body carries message history
- `GET /api/videos/{id}/stream` - serves the video file with HTTP range support (required for seeking)

Frontend: Vite + React + TypeScript. One page, three states:

1. **Upload**: drop zone, file validation, upload progress.
2. **Processing**: live stage checklist (transcribing / analyzing visuals / summarizing) with elapsed time.
3. **Workspace**: video player left; right panel scroller with tabs (Transcript / Visual / Moments) that auto-scrolls in sync with playback and highlights the current record; chat panel below; clicking any timestamp or citation seeks the player.

Design quality matters: this is a sales demo. Fox-appropriate dark broadcast aesthetic, no generic AI look. Frontend design skill applies at implementation time.

Secrets: `.env` file with `ELEVENLABS_API_KEY`, `GOOGLE_API_KEY`, `ANTHROPIC_API_KEY`. Startup fails fast with a clear message if any is missing. `.env` is gitignored.

## Error Handling

- Pipeline stages are idempotent and resumable; state lives in `videos.status`.
- Per-chunk retry for Gemini windows; a failed window retries alone, not the whole video.
- Upload validation: extension/container check, duration probe, reject >3 hours or >2 GB for MVP.
- Chat: if a citation timestamp exceeds video duration, drop the link and log it.
- All external API errors logged with request ids; user-facing messages stay friendly.

## Testing (3-day scope)

- Smoke test: a 2-5 minute Spanish sports clip runs the whole pipeline before the real video does.
- Golden checks after each processing run: transcript non-empty and >1 speaker found; visual events cover >=90% of duration; every minute has a summary; all timestamps within duration.
- Chat eval: 10 prepared questions (including 2 unanswerable ones) checked by hand; unanswerable ones must return "not in the data".
- Demo rehearsal on day 3 with the real video and prepared killer questions.

## Costs

- Demo video (2h): ~$3 processing, cents per chat question.
- Production per hour of video: ~$1.40 on demand, ~$0.90 batched.
- Production example, 3 channels 24/7 (72 hr/day): ~$65-100/day, $2-3K/month AI cost. Infrastructure (VM, storage, Postgres) adds roughly $200-500/month at that scale.

## Production Path (not built now, told to the boss)

1. Connector to Fox's video storage (platform TBD, cousin confirming) replaces manual upload.
2. Postgres + pgvector replaces SQLite; embeddings enable search across the whole vault.
3. Job queue (per-video jobs, stateless workers) enables continuous 24/7 ingestion; workers scale horizontally.
4. Gemini batch mode halves visual-analysis cost.
5. Multi-video chat: retrieval (hybrid keyword + vector) selects relevant records across all broadcasts, then the same grounded-answer approach.
6. Later products reuse the vault: AI content generator, reporting, model training data.

## Day Plan

- Day 1 (2026-07-02): accounts + keys, pipeline stages 1-6 working on a short test clip; process the real video overnight when it arrives.
- Day 2 (2026-07-03): web app; workspace UI with synced scroller and chat with seeking citations.
- Day 3 (2026-07-04): polish, error hardening, golden checks, demo rehearsal.

## Open Items

- Bernardo creates ElevenLabs, Google AI Studio, and Anthropic accounts today.
- Cousin confirms Fox's storage platform (for the production pitch, not the MVP).
- Real video arrives 2026-07-02; smoke test must not wait for it.
