# LINEAR_PLAYBOOK — Verdandi team habits (SearXNG-backed, 2026-09-11)

Project: Verdandi (was anomaly-twin-trace → ForgeTrace). Team: MCP (keep 1 team; 250-issue free limit — archive Done promptly). 7 milestones M0–M5 + dates. 9 issues MCP-10–18 with dependency DAG.

## What I (agent) configured via API
Labels (8, max): type:feature/bug/spike/docs + area:twin/detect/narrate/eval. Issues carry Goal/Tasks/Files/Cases/Kill-bars/Exit/Docs + blockedBy chains + estimates + priorities. Project description + GitHub link + milestones live.

## UI-only steps (you click — no API exists)
1. **GitHub integration**: Linear Settings → Integrations → GitHub → Connect (org owner) → grant ONLY Verdandi repo → DISABLE Issues Sync (keep PR/commit linking ON).
2. **Workflow automations**: Teams → MCP → Workflow: PR opened → In Progress; review requested → In Review; merged to main → Done; closed unmerged → Canceled.
3. **Cycles**: enable 2-week cycles, start Monday, auto-rollover ON (6–7 cycles/semester). Pull milestone issues into each cycle; unfinished rolls — review, don't delete.
4. **Triage**: enable; rotate reviewer weekly; Accept/Duplicate/Decline on sight, assign owner+priority on accept.
5. **SLA**: if plan allows — Urgent 48h, High 1wk; else skip (priority + milestones cover it).
6. **Views** (save): My Work · Current Cycle by Assignee (standup) · By Milestone · In Review stale>2d · Blocked.
7. **Project Updates**: weekly Friday 🟢/🟡/🔴 + next kill-bar.

## Branch + PR conventions (auto-link magic)
- Branch per issue: `Copy git branch` → contains `MCP-<ID>` (e.g. `shreyasjoshi2511/mcp-12-...`) → auto-links.
- PR title/body MUST say `Fixes MCP-12` (closing) or `Related to MCP-12` (link-only). Merge to `main` auto-moves issue Done. Revert re-opens.
- Small PRs; link docs/ changes in same PR; paste PR link back to the issue.

## Rituals (15–20 min)
- Mon: triage → Backlog/Todo, assign milestone/cycle/estimate. Mid-week async: PR actions move status; comment blockers. Fri: demo + project update + archive Done.

## Rules
- 1 issue ≤ 1 cycle; split bigger. Priority = urgency only (Urgent = kill-bar blocked). WIP ≤3/person. Definition of Ready: title+acceptance+milestone+estimate+owner+unblocked. Done: merged via magic word + CI green + docs updated.
