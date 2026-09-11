# PROTOCOL.md — Canonical copy (memory-architecture §§4–9, condensed pointer)

Authority: `~/.config/opencode/skills/elenchus/references/memory-architecture.md` wins on conflict.
Memory root: `~/projects/anomaly-twin-trace/.opencode/blackboard/anomaly-twin-trace/`

## Roles / Write permissions
- Orchestrator: BLACKBOARD.md, DECISIONS.md, promoted EVIDENCE.md, final PLAN.md. Never WORKER-*.md.
- Worker (explore/librarian/prosecutor/defense): own WORKER-*.md + append MESSAGES.md. Never BLACKBOARD/EVIDENCE/DECISIONS directly.
- User: answers/picks/approvals relayed into DECISIONS.md.

## Message bus (MESSAGES.md, append-only)
`## <UTC-timestamp> <sender>→<recipient|ALL> [<CLAIM|QUESTION|CHALLENGE|HANDOFF>]` body ≤15 lines. Never edit/delete.

## Claim-Before-Write
Append `INTENT: <rq|domain>` before sweep; earliest timestamp owns primary; second pivots orthogonal.

## Distill-Not-Dump
Worker return ≤1,500 tokens (verdict + 3–7 bullets + URLs + tier + file refs). Raw crawls stay in WORKER-*.md; distill to EVIDENCE.md then DELETE scratch. Claims need ≥2 independent Tier-1/2 domains or sandbox execution. Stage-boundary compaction: BLACKBOARD ≤75 lines, Pinned Invariants preserved verbatim.

## Claim FSM
Hypothesized → Under_Investigation → Corroborated | Falsified (negative invariant) | Contested (spike) | Unresolved (gap-map.md).

## BLACKBOARD shape
`# <slug> — Phase: <DISCOVER|FRAME|RESEARCH|ATAM|SPIKE|DECIDE|PLAN|DONE>` + Pinned Invariants (immune) + Goal(1 line) + Active Claims + Blockers + Single Next Action.

## Verification
Orchestrator verifies every CLAIM (token cap, ≥1 URL or exec output, inversion executed). 2 fails → escalate to user or gap-map.md; no blind third retry.
