# Fox Video Intelligence

Turns a sports broadcast into structured data (diarized transcript, visual
events, summaries, key moments) and answers questions about it with an AI
grounded in that data. Citations seek the video to the exact moment.

## Stack

ElevenLabs Scribe v2 (Spanish diarized transcription) + Gemini 3.5 Flash
(native video analysis) + Claude Opus 4.8 (grounded chat). FastAPI + SQLite
backend, Vite + React frontend. Design spec:
`docs/superpowers/specs/2026-07-02-video-intelligence-mvp-design.md`.

## Prerequisites

- Python 3.11+, Node 20+, ffmpeg on PATH
- API keys: ElevenLabs, Google AI Studio, Anthropic

## Run

Backend:

    cd backend
    python -m venv .venv
    .venv\Scripts\pip install -r requirements.txt
    copy .env.example .env   (fill in the three keys)
    .venv\Scripts\uvicorn app.main:build --factory --port 8000

Frontend:

    cd frontend
    npm install
    npm run dev

Open http://localhost:5173, upload a video, wait for processing, ask
questions.

## Tests

    cd backend && .venv\Scripts\python -m pytest
    cd frontend && npm test

After processing a real video:

    cd backend && .venv\Scripts\python scripts/golden_check.py <video_id>

## Costs

Roughly $1.40 per hour of video processed. Chat questions cost cents.
