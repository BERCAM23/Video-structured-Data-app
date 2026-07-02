# Product: Video Intelligence Pipeline + Grounded AI Search

## One-line

Every video Fox transmits gets analyzed by AI into structured data, and a private AI answers questions about any moment of any broadcast, citing the exact clip and timestamp.

## The Pipeline (per video)

1. **Ingest**: pull video from Fox's existing storage (likely their cloud bucket, see open questions).
2. **Transcribe with speaker diarization**: full transcript, each line attributed to a speaker (e.g. narrator Martinoli vs analyst), with timestamps.
3. **Visual analysis**: a frame or scene description every few seconds (MVP target: every 3 to 5 seconds) describing what is happening on screen.
4. **Periodic summaries**: a rolled-up summary every minute, plus a whole-video summary and classification (sport, teams, show, event type).
5. **Structured output**: everything lands as structured data (JSON records with video id, timestamp ranges, speaker, text, visual description, summary level).

## The Context Vault (Fox's data asset)

The structured records accumulate into a queryable corpus of everything Fox has aired. This is the durable asset. Uses:

- Semantic + keyword search over all broadcasts
- Grounding corpus for a private AI (RAG over the records, vector database if warranted)
- Future model training data
- Reporting, content strategy, compliance review

## The Search / Q&A Experience

A user asks in natural language. Example from Bernardo: "What was the part where the narrator jumped out of the chair and said wow, that is incredible?" The AI must:

1. Find the moment (speaker = Martinoli, the quote, the excitement)
2. Answer with the specifics: who said it, what exactly was said, in which broadcast, at which timestamp
3. Link back to the actual video clip

Answers must be grounded only in the structured data. No invented facts.

## Non-negotiable Requirements

- **Scalable**: Fox transmits 24/7. The architecture must handle continuous ingestion, not one-off jobs.
- **Cost-transparent**: per-hour-of-video processing cost must be known and predictable, because pricing to Fox depends on it.
- **Referenceable**: every AI answer must point to video id + timestamp.

## Status

Design approved 2026-07-02. Spec: `docs/superpowers/specs/2026-07-02-video-intelligence-mvp-design.md`. Stack: ElevenLabs Scribe v2 (diarized Spanish transcript, $0.22/hr) + Gemini 3.5 Flash (native video analysis, ~$1.00/hr) + Claude Opus 4.8 (grounded chat). Processing cost ~$1.40/hr of video, ~$0.90/hr batched at scale.
