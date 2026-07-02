# MVP Definition

## Purpose

Show the cousin's boss the core loop working on a real Fox video so he hires the service. The MVP is a sales weapon, not a product.

## Deadline

**3 days from 2026-07-02. Ready to work by 2026-07-05.** The sample video arrives from the cousin on 2026-07-02.

## Demo Format (decided 2026-07-02)

One page, data-first:

1. Video upload.
2. Video player with a scroller of the structured data on the right, synced to playback.
3. Chat with the AI below. Answers cite timestamps; clicking a citation seeks the video to that exact moment.

Priority is extracting real, valuable data from the video. UI serves the data, not the other way around.

## Scope (exactly this, nothing more)

Input: **one real video** provided by the cousin directly from Fox.

The system produces:

1. **Diarized transcript**: full transcript with speaker labels and timestamps.
2. **Frame analysis**: a visual description every 3 to 5 seconds of what is happening on screen.
3. **Minute summaries**: an overall summary for every minute of video.
4. **Structured data**: all of the above stored as structured records (JSON / database), not loose text.
5. **Grounded chat**: an AI you can ask about the video right there. It answers strictly from the structured data and cites timestamps. RAG-style; vector database only if it earns its place at this scale.

## Success Criteria

- The boss asks a question about a specific moment and gets a correct, specific, timestamped answer.
- The demo makes the 24/7 production version obvious and desirable.
- Processing cost for the demo video is measured and recorded, so we can quote per-hour pricing.

## Out of Scope for MVP

- Multi-video ingestion, live stream ingestion
- Connecting to Fox's storage
- User accounts, permissions
- AI content generator (see `04-future-products.md`)
