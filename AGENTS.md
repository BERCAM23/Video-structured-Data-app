# Agent Instructions

This file is for any AI agent joining this project (Claude, Codex, Gemini, or other). CLAUDE.md contains the same rules for Claude Code specifically.

## What this project is

An AI services engagement for Fox. Two people run it: Bernardo (technical, builds everything) and his cousin (Fox Media team insider, moving to the US for a master's degree; his boss wants to hire services from us to keep the relationship).

Product one, the immediate sell: a video intelligence pipeline. Every video Fox transmits gets analyzed into structured data (diarized transcripts, timestamped frame descriptions, periodic summaries). That data forms a "context vault" for Fox. On top of it sits a private AI that answers natural language questions grounded in the data, with references to the exact clip and timestamp.

## How to work here

1. Read `vault/INDEX.md` first, then only the vault files your task needs.
2. `vault/` is the single source of truth. Chat history is not.
3. Decisions go in `vault/06-decisions.md` (date, decision, reason).
4. Unresolved items live in `vault/05-open-questions.md`. Do not assume answers to anything listed there.
5. Design and planning docs go in `docs/`.
6. Writing style: short direct sentences, no em dashes, numbers over adjectives, no hedging.

## Vault map

| File | Contents |
|------|----------|
| `vault/01-business-context.md` | Who is involved, the Fox relationship, business model |
| `vault/02-product-video-intelligence.md` | Core product definition and pipeline |
| `vault/03-mvp.md` | MVP scope and success criteria |
| `vault/04-future-products.md` | AI content generator, employee AI assistant |
| `vault/05-open-questions.md` | Unresolved questions, do not assume |
| `vault/06-decisions.md` | Decision log |
