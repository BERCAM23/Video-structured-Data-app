# Fox Video Intelligence Project

AI agency engagement serving Fox (via Bernardo's cousin on the Fox Media team). First product: a video intelligence pipeline that turns every transmitted video into structured, searchable data plus a private AI that answers questions grounded in that data.

## Session Start (mandatory)

1. Read `vault/INDEX.md` first. It is one line per vault file.
2. Read only the vault files relevant to your task. Do not read the whole vault by default.
3. Check `vault/06-decisions.md` before proposing anything already decided.
4. Check `vault/05-open-questions.md` before assuming anything listed there.

## The Context Vault

`vault/` is the single source of truth for business context, product definition, and decisions. Rules:

- Every meaningful decision gets logged in `vault/06-decisions.md` with date, decision, and reason.
- When an open question gets answered, move it from `05-open-questions.md` into the relevant file and log the decision.
- New durable knowledge goes into the vault, not into chat history. If it matters next session, it goes in a file.
- Keep vault files small and focused. Split before a file passes 300 lines.
- Never contradict the vault silently. If reality changed, update the vault and say so.

## Current Phase

Design and MVP. Nothing is built yet. The MVP definition lives in `vault/03-mvp.md`. Design docs live in `docs/`.

## Writing Style (all output)

- Direct, short sentences. One idea per sentence.
- Never use em dashes.
- Specifics over generalities. Numbers over adjectives.
- No hedging phrases.

## Lessons Learned

- 2026-07-02: Fable burned tokens transcribing plan code inline until Bernardo interrupted. Rule: implementation executes via Sonnet subagents transcribing from the plan; Fable only plans, orchestrates, and reviews (test runs, diff stats, targeted reads). Batch several tasks per subagent to amortize the plan read.
