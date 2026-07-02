# Open Questions

Do not assume answers to anything here. Ask Bernardo or the cousin.

## Infrastructure

- **"WSC" storage**: Bernardo does not know the exact platform name. Cousin must confirm what it is and whether we can get read access. Design stays storage-agnostic until confirmed. (Asked 2026-07-02.)

## Content

- Confirmed 2026-07-02: Fox Sports Latin America, Spanish-language sports broadcasts. Remaining: which country feed, live vs VOD mix, typical video length, and hours transmitted per day (needed for production cost model).

## Commercial

- Pricing model to Fox: per hour of video processed, monthly retainer, or both?
- Contract and data handling: NDAs, where can Fox's video legally be uploaded (third-party AI APIs?), any restriction on cloud providers or regions?
- When does the cousin leave for the US?

## Technical

Resolved 2026-07-02. Models, costs, and MVP stack are in the design spec: `docs/superpowers/specs/2026-07-02-video-intelligence-mvp-design.md`. Summary: ElevenLabs Scribe v2 + Gemini 3.5 Flash + Claude Opus 4.8; no vector DB in MVP; MVP runs on Bernardo's machine.

Still open:
- Bernardo to create ElevenLabs, Google AI Studio, and Anthropic accounts (needed day 1).
