# Decision Log

Format: date, decision, reason. Newest on top.

## 2026-07-02: MVP code complete on day 1

All 15 plan tasks built, tested (32 backend + 3 frontend tests green), and pushed to https://github.com/BERCAM23/Video-structured-Data-app. Remaining before demo: API keys in backend/.env, live STT verification, end-to-end run with the real Fox video, golden checks, 10-question chat eval, day-3 design polish.

## 2026-07-02: Hybrid architecture approved

ElevenLabs Scribe v2 for diarized Spanish transcripts ($0.22/hr), Gemini 3.5 Flash for native video analysis (~$1.00/hr), Gemini Flash for summaries (~$0.15/hr), Claude Opus 4.8 for grounded chat. Total ~$1.40/hr on demand, ~$0.90/hr batched. Reason: the flagship "who said it" query needs Spanish diarization with word timestamps, which Gemini alone cannot deliver; all-Anthropic costs 3-5x on visuals. Rejected: all-Gemini, all-Anthropic. No vector DB in MVP; pgvector planned for production. Full spec: `docs/superpowers/specs/2026-07-02-video-intelligence-mvp-design.md`.

## 2026-07-02: Content confirmed as Fox Sports LatAm, Spanish

All model selection (transcription, diarization, vision) optimizes for Spanish sports commentary: fast speech, high emotion, crowd noise. Reason: Bernardo confirmed directly.

## 2026-07-02: MVP deadline is 3 days

Demo must be ready to work by 2026-07-05. Reason: Bernardo committed to it. Consequence: simplest stack that works, one-pass processing, no infra beyond what the demo needs.

## 2026-07-02: Demo layout fixed

Single page: upload, video player + synced structured-data scroller on the right, chat below with timestamp citations that seek the video. Reason: Bernardo specified it; the data is the star, the seek-on-citation is the wow moment.

## 2026-07-02: MVP scope frozen

One real Fox video in; diarized transcript + frame descriptions every 3 to 5 seconds + minute summaries + structured records + grounded chat with timestamp citations. Reason: this is the minimum that makes the boss see the production value. Everything else (multi-video, live ingestion, storage integration) waits.

## 2026-07-02: Product sequence

Video intelligence pipeline first, AI content generator and employee assistants later. Reason: the boss can hire the search engine immediately; the rest are follow-on sales.

## 2026-07-02: Vault established

All durable project knowledge lives in `vault/`, indexed by `INDEX.md`, with decisions logged here. Reason: multiple agents and sessions will work on this project and need one source of truth.
